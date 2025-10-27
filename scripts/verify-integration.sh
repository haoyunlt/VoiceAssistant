#!/bin/bash
# 验证服务集成的脚本

set -e

echo "🔍 验证架构优化..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查直连OpenAI的代码
echo -e "\n${YELLOW}[1/6] 检查直连OpenAI的代码...${NC}"
OPENAI_DIRECT=$(grep -r "from openai import\|AsyncOpenAI" algo/ \
  --exclude-dir=model-adapter \
  --exclude-dir=__pycache__ \
  --include="*.py" \
  2>/dev/null | grep -v "openai_client.py" | wc -l || true)

if [ "$OPENAI_DIRECT" -gt 0 ]; then
  echo -e "${RED}❌ 发现 $OPENAI_DIRECT 处直连OpenAI的代码${NC}"
  grep -r "from openai import\|AsyncOpenAI" algo/ \
    --exclude-dir=model-adapter \
    --exclude-dir=__pycache__ \
    --include="*.py" \
    2>/dev/null | grep -v "openai_client.py" || true
else
  echo -e "${GREEN}✅ 无直连OpenAI代码${NC}"
fi

# 2. 检查直连Milvus的代码
echo -e "\n${YELLOW}[2/6] 检查直连Milvus的代码...${NC}"
MILVUS_DIRECT=$(grep -r "from pymilvus import\|MilvusClient\|connections.connect" algo/ \
  --exclude-dir=vector-store-adapter \
  --exclude-dir=__pycache__ \
  --include="*.py" \
  2>/dev/null | wc -l || true)

if [ "$MILVUS_DIRECT" -gt 0 ]; then
  echo -e "${RED}❌ 发现 $MILVUS_DIRECT 处直连Milvus的代码${NC}"
  grep -r "from pymilvus import\|MilvusClient\|connections.connect" algo/ \
    --exclude-dir=vector-store-adapter \
    --exclude-dir=__pycache__ \
    --include="*.py" \
    2>/dev/null || true
else
  echo -e "${GREEN}✅ 无直连Milvus代码${NC}"
fi

# 3. 检查UnifiedLLMClient的使用
echo -e "\n${YELLOW}[3/6] 检查UnifiedLLMClient的使用...${NC}"
UNIFIED_CLIENT=$(grep -r "UnifiedLLMClient" algo/ \
  --exclude-dir=__pycache__ \
  --include="*.py" \
  2>/dev/null | wc -l || true)

echo -e "${GREEN}✅ 找到 $UNIFIED_CLIENT 处使用UnifiedLLMClient${NC}"

# 4. 检查环境变量配置
echo -e "\n${YELLOW}[4/6] 检查环境变量配置...${NC}"
if [ -f ".env.example" ]; then
  echo -e "${GREEN}✅ .env.example 存在${NC}"
  
  # 检查关键环境变量
  VARS=("MODEL_ADAPTER_URL" "RETRIEVAL_SERVICE_URL" "VECTOR_STORE_ADAPTER_URL")
  for VAR in "${VARS[@]}"; do
    if grep -q "^$VAR=" .env.example; then
      echo -e "  ${GREEN}✓${NC} $VAR"
    else
      echo -e "  ${RED}✗${NC} $VAR"
    fi
  done
else
  echo -e "${RED}❌ .env.example 不存在${NC}"
fi

# 5. 检查服务集成配置
echo -e "\n${YELLOW}[5/6] 检查服务集成配置...${NC}"
if [ -f "configs/services-integration.yaml" ]; then
  echo -e "${GREEN}✅ services-integration.yaml 存在${NC}"
else
  echo -e "${RED}❌ services-integration.yaml 不存在${NC}"
fi

# 6. 检查Docker配置
echo -e "\n${YELLOW}[6/6] 检查Docker配置...${NC}"
if [ -f "docker-compose.override.yml" ]; then
  echo -e "${GREEN}✅ docker-compose.override.yml 存在${NC}"
  
  # 验证配置
  if command -v docker-compose &> /dev/null; then
    docker-compose config > /dev/null 2>&1 && \
      echo -e "  ${GREEN}✓${NC} Docker Compose配置有效" || \
      echo -e "  ${RED}✗${NC} Docker Compose配置无效"
  fi
else
  echo -e "${RED}❌ docker-compose.override.yml 不存在${NC}"
fi

# 总结
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}验证完成！${NC}"
echo -e "${GREEN}========================================${NC}"

if [ "$OPENAI_DIRECT" -gt 0 ] || [ "$MILVUS_DIRECT" -gt 0 ]; then
  echo -e "${RED}⚠️  发现需要修复的问题${NC}"
  exit 1
else
  echo -e "${GREEN}✅ 所有检查通过${NC}"
  exit 0
fi

