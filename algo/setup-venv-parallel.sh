#!/bin/bash

# 并行为所有算法服务创建 Python 3.11 虚拟环境
# 更快速的虚拟环境设置脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 算法服务列表
SERVICES=(
    "agent-engine"
    "indexing-service"
    "knowledge-service"
    "model-adapter"
    "multimodal-engine"
    "rag-engine"
    "retrieval-service"
    "vector-store-adapter"
    "voice-engine"
)

echo "=========================================="
echo "并行设置算法服务 Python 3.11 虚拟环境"
echo "=========================================="
echo ""

# 检查 Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}错误: Python 3.11 未安装${NC}"
    echo "macOS 安装: brew install python@3.11"
    exit 1
fi

PYTHON_VERSION=$(python3.11 --version)
echo -e "${GREEN}✓ 找到 $PYTHON_VERSION${NC}"
echo ""

# 设置 pip 配置（使用国内镜像）
export PIP_CONFIG_FILE="$SCRIPT_DIR/pip.conf"
if [ -f "$PIP_CONFIG_FILE" ]; then
    echo -e "${BLUE}使用 pip 配置: $PIP_CONFIG_FILE${NC}"
    echo ""
fi

# 函数：为单个服务设置虚拟环境
setup_service() {
    local service=$1
    local SERVICE_DIR="$SCRIPT_DIR/$service"
    local LOG_FILE="$SCRIPT_DIR/.venv-setup-${service}.log"

    # 检查目录和 requirements.txt
    if [ ! -d "$SERVICE_DIR" ]; then
        echo -e "${YELLOW}⚠ $service: 目录不存在${NC}" | tee -a "$LOG_FILE"
        return 1
    fi

    if [ ! -f "$SERVICE_DIR/requirements.txt" ]; then
        echo -e "${YELLOW}⚠ $service: requirements.txt 不存在${NC}" | tee -a "$LOG_FILE"
        return 1
    fi

    cd "$SERVICE_DIR"

    # 删除旧虚拟环境
    if [ -d "venv" ]; then
        rm -rf venv
    fi

    # 创建虚拟环境
    if ! python3.11 -m venv venv >> "$LOG_FILE" 2>&1; then
        echo -e "${RED}✗ $service: 虚拟环境创建失败${NC}" | tee -a "$LOG_FILE"
        return 1
    fi

    # 激活并安装依赖
    source venv/bin/activate

    if ! pip install --upgrade pip >> "$LOG_FILE" 2>&1; then
        echo -e "${RED}✗ $service: pip 升级失败${NC}" | tee -a "$LOG_FILE"
        deactivate
        return 1
    fi

    if ! pip install -r requirements.txt >> "$LOG_FILE" 2>&1; then
        echo -e "${RED}✗ $service: 依赖安装失败，查看日志: $LOG_FILE${NC}"
        deactivate
        return 1
    fi

    deactivate
    echo -e "${GREEN}✓ $service: 完成${NC}"
    return 0
}

# 导出函数供并行使用
export -f setup_service
export SCRIPT_DIR RED GREEN YELLOW BLUE NC

# 串行处理每个服务（更稳定）
SUCCESS=0
FAILED=0
SKIPPED=0

for service in "${SERVICES[@]}"; do
    echo "处理: $service ..."

    if setup_service "$service"; then
        ((SUCCESS++))
    else
        if [ -f "$SCRIPT_DIR/.venv-setup-${service}.log" ] && grep -q "不存在" "$SCRIPT_DIR/.venv-setup-${service}.log"; then
            ((SKIPPED++))
        else
            ((FAILED++))
        fi
    fi
    echo ""
done

# 清理日志文件
echo "清理临时日志文件..."
rm -f "$SCRIPT_DIR/.venv-setup-"*.log

# 统计
echo "=========================================="
echo "虚拟环境设置完成"
echo "=========================================="
echo "总计: ${#SERVICES[@]}"
echo -e "${GREEN}成功: $SUCCESS${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo -e "${YELLOW}跳过: $SKIPPED${NC}"
echo ""

if [ $SUCCESS -gt 0 ]; then
    echo -e "${GREEN}✓ 虚拟环境设置成功！${NC}"
    echo ""
    echo "激活方法:"
    echo "  cd algo/<service-name>"
    echo "  source venv/bin/activate"
    echo ""
    echo "查看 Python 版本:"
    echo "  python --version"
    exit 0
else
    echo -e "${RED}✗ 虚拟环境设置失败${NC}"
    exit 1
fi
