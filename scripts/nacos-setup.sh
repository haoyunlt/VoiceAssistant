#!/bin/bash
# Nacos 配置中心设置脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认配置
NACOS_ADDR="${NACOS_ADDR:-localhost:8848}"
NACOS_USERNAME="${NACOS_USERNAME:-nacos}"
NACOS_PASSWORD="${NACOS_PASSWORD:-nacos}"
NACOS_NAMESPACE="${NACOS_NAMESPACE:-}"
NACOS_GROUP="${NACOS_GROUP:-VoiceAssistant}"

# 配置文件目录
CONFIG_DIR="./configs"

# 要上传的服务配置
SERVICES=(
  "conversation-service"
  "agent-engine"
  "model-adapter"
  "retrieval-service"
  "indexing-service"
  "rag-engine"
)

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Nacos 配置中心初始化脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 函数：检查 Nacos 是否可用
check_nacos() {
  echo -e "${YELLOW}检查 Nacos 连接...${NC}"
  if curl -s "http://${NACOS_ADDR}/nacos/" > /dev/null; then
    echo -e "${GREEN}✅ Nacos 连接成功${NC}"
    return 0
  else
    echo -e "${RED}❌ 无法连接到 Nacos: http://${NACOS_ADDR}${NC}"
    return 1
  fi
}

# 函数：登录 Nacos 获取 Token
nacos_login() {
  echo -e "${YELLOW}登录 Nacos...${NC}"
  TOKEN=$(curl -s -X POST "http://${NACOS_ADDR}/nacos/v1/auth/login" \
    -d "username=${NACOS_USERNAME}" \
    -d "password=${NACOS_PASSWORD}" | grep -o '"accessToken":"[^"]*' | cut -d'"' -f4)

  if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✅ 登录成功${NC}"
    export NACOS_TOKEN="$TOKEN"
  else
    echo -e "${YELLOW}⚠️  获取 Token 失败，可能 Nacos 未启用鉴权${NC}"
    export NACOS_TOKEN=""
  fi
}

# 函数：发布配置到 Nacos
publish_config() {
  local service_name=$1
  local config_file="${CONFIG_DIR}/${service_name}.yaml"
  local data_id="${service_name}.yaml"

  if [ ! -f "$config_file" ]; then
    echo -e "${YELLOW}⚠️  配置文件不存在: ${config_file}${NC}"
    return 1
  fi

  echo -e "${YELLOW}上传配置: ${data_id}${NC}"

  # 读取配置文件内容（去掉 nacos 配置块）
  content=$(python3 -c "
import yaml
with open('${config_file}', 'r') as f:
    data = yaml.safe_load(f)
    if 'nacos' in data:
        del data['nacos']
    print(yaml.dump(data, allow_unicode=True))
" 2>/dev/null || cat "$config_file")

  # 发布配置
  response=$(curl -s -X POST "http://${NACOS_ADDR}/nacos/v1/cs/configs" \
    -H "Authorization: Bearer ${NACOS_TOKEN}" \
    -d "dataId=${data_id}" \
    -d "group=${NACOS_GROUP}" \
    -d "content=${content}" \
    -d "type=yaml" \
    -d "tenant=${NACOS_NAMESPACE}")

  if [ "$response" = "true" ]; then
    echo -e "${GREEN}✅ 配置上传成功: ${data_id}${NC}"
    return 0
  else
    echo -e "${RED}❌ 配置上传失败: ${data_id}${NC}"
    echo "响应: $response"
    return 1
  fi
}

# 函数：验证配置
verify_config() {
  local service_name=$1
  local data_id="${service_name}.yaml"

  echo -e "${YELLOW}验证配置: ${data_id}${NC}"

  response=$(curl -s "http://${NACOS_ADDR}/nacos/v1/cs/configs" \
    -H "Authorization: Bearer ${NACOS_TOKEN}" \
    -G \
    --data-urlencode "dataId=${data_id}" \
    --data-urlencode "group=${NACOS_GROUP}" \
    --data-urlencode "tenant=${NACOS_NAMESPACE}")

  if [ -n "$response" ] && [ "$response" != "config data not exist" ]; then
    echo -e "${GREEN}✅ 配置验证成功${NC}"
    return 0
  else
    echo -e "${RED}❌ 配置验证失败${NC}"
    return 1
  fi
}

# 函数：列出所有配置
list_configs() {
  echo -e "${YELLOW}获取配置列表...${NC}"

  response=$(curl -s "http://${NACOS_ADDR}/nacos/v1/cs/configs" \
    -H "Authorization: Bearer ${NACOS_TOKEN}" \
    -G \
    --data-urlencode "pageNo=1" \
    --data-urlencode "pageSize=100" \
    --data-urlencode "group=${NACOS_GROUP}" \
    --data-urlencode "tenant=${NACOS_NAMESPACE}")

  echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
}

# 主流程
main() {
  echo "配置信息:"
  echo "  Nacos 地址: ${NACOS_ADDR}"
  echo "  命名空间: ${NACOS_NAMESPACE:-public}"
  echo "  分组: ${NACOS_GROUP}"
  echo "  配置目录: ${CONFIG_DIR}"
  echo ""

  # 检查 Nacos 连接
  if ! check_nacos; then
    echo ""
    echo "请确保 Nacos 已启动："
    echo "  docker run -d --name nacos -p 8848:8848 -e MODE=standalone nacos/nacos-server:v2.3.0"
    exit 1
  fi

  # 登录 Nacos
  nacos_login
  echo ""

  # 上传配置
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}开始上传配置${NC}"
  echo -e "${GREEN}========================================${NC}"

  success_count=0
  fail_count=0

  for service in "${SERVICES[@]}"; do
    echo ""
    if publish_config "$service"; then
      ((success_count++))
      verify_config "$service"
    else
      ((fail_count++))
    fi
  done

  # 汇总
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}配置上传完成${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo "成功: ${success_count}"
  echo "失败: ${fail_count}"
  echo ""

  # 列出所有配置
  if [ "$1" = "--list" ] || [ "$1" = "-l" ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}配置列表${NC}"
    echo -e "${GREEN}========================================${NC}"
    list_configs
  fi

  # 使用说明
  echo ""
  echo -e "${YELLOW}========================================${NC}"
  echo -e "${YELLOW}使用说明${NC}"
  echo -e "${YELLOW}========================================${NC}"
  echo "1. 访问 Nacos 控制台: http://${NACOS_ADDR}/nacos"
  echo "2. 账号/密码: ${NACOS_USERNAME}/${NACOS_PASSWORD}"
  echo "3. 查看配置: 配置管理 -> 配置列表 -> 分组: ${NACOS_GROUP}"
  echo ""
  echo "启动服务（Nacos 模式）："
  echo "  export CONFIG_MODE=nacos"
  echo "  export NACOS_SERVER_ADDR=${NACOS_ADDR%:*}"
  echo "  export NACOS_GROUP=${NACOS_GROUP}"
  echo "  ./your-service"
  echo ""
}

# 帮助信息
show_help() {
  echo "用法: $0 [选项]"
  echo ""
  echo "选项:"
  echo "  -h, --help     显示帮助信息"
  echo "  -l, --list     上传后列出所有配置"
  echo ""
  echo "环境变量:"
  echo "  NACOS_ADDR       Nacos 地址 (默认: localhost:8848)"
  echo "  NACOS_USERNAME   Nacos 用户名 (默认: nacos)"
  echo "  NACOS_PASSWORD   Nacos 密码 (默认: nacos)"
  echo "  NACOS_NAMESPACE  Nacos 命名空间 (默认: public)"
  echo "  NACOS_GROUP      Nacos 分组 (默认: VoiceAssistant)"
  echo ""
  echo "示例:"
  echo "  # 使用默认配置"
  echo "  $0"
  echo ""
  echo "  # 指定 Nacos 地址和命名空间"
  echo "  NACOS_ADDR=nacos.example.com:8848 NACOS_NAMESPACE=prod $0"
  echo ""
  echo "  # 上传后列出配置"
  echo "  $0 --list"
}

# 命令行参数处理
case "${1:-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  *)
    main "$@"
    ;;
esac
