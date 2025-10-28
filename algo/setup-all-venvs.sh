#!/bin/bash

# 为所有算法服务创建 Python 3.11 虚拟环境
# 统一虚拟环境设置脚本

set -e

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
echo "设置所有算法服务的 Python 3.11 虚拟环境"
echo "=========================================="
echo ""

# 检查 Python 3.11 是否安装
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}错误: Python 3.11 未安装${NC}"
    echo "请先安装 Python 3.11"
    echo ""
    echo "macOS 安装方法:"
    echo "  brew install python@3.11"
    echo ""
    exit 1
fi

# 显示 Python 版本
PYTHON_VERSION=$(python3.11 --version)
echo -e "${GREEN}✓ 找到 $PYTHON_VERSION${NC}"
echo ""

# 统计信息
TOTAL=${#SERVICES[@]}
SUCCESS=0
FAILED=0
SKIPPED=0

# 为每个服务设置虚拟环境
for service in "${SERVICES[@]}"; do
    SERVICE_DIR="$SCRIPT_DIR/$service"

    echo "------------------------------------------"
    echo "处理服务: $service"
    echo "------------------------------------------"

    # 检查服务目录是否存在
    if [ ! -d "$SERVICE_DIR" ]; then
        echo -e "${YELLOW}⚠ 跳过: 目录不存在${NC}"
        ((SKIPPED++))
        echo ""
        continue
    fi

    # 检查 requirements.txt 是否存在
    if [ ! -f "$SERVICE_DIR/requirements.txt" ]; then
        echo -e "${YELLOW}⚠ 跳过: requirements.txt 不存在${NC}"
        ((SKIPPED++))
        echo ""
        continue
    fi

    cd "$SERVICE_DIR"

    # 如果虚拟环境已存在，询问是否重新创建
    if [ -d "venv" ]; then
        echo -e "${YELLOW}虚拟环境已存在，将删除并重新创建${NC}"
        rm -rf venv
    fi

    # 创建虚拟环境
    echo "创建虚拟环境..."
    if python3.11 -m venv venv; then
        echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
    else
        echo -e "${RED}✗ 虚拟环境创建失败${NC}"
        ((FAILED++))
        echo ""
        continue
    fi

    # 激活虚拟环境并安装依赖
    echo "安装依赖..."
    if source venv/bin/activate && \
       pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null 2>&1 && \
       pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; then
        echo -e "${GREEN}✓ 依赖安装成功${NC}"
        ((SUCCESS++))
        deactivate
    else
        echo -e "${RED}✗ 依赖安装失败${NC}"
        ((FAILED++))
        deactivate 2>/dev/null || true
    fi

    echo ""
done

# 输出统计信息
echo "=========================================="
echo "虚拟环境设置完成"
echo "=========================================="
echo -e "总计服务: $TOTAL"
echo -e "${GREEN}成功: $SUCCESS${NC}"
echo -e "${RED}失败: $FAILED${NC}"
echo -e "${YELLOW}跳过: $SKIPPED${NC}"
echo ""

if [ $SUCCESS -eq $TOTAL ]; then
    echo -e "${GREEN}✓ 所有服务的虚拟环境设置成功！${NC}"
    echo ""
    echo "激活虚拟环境的方法:"
    echo "  cd algo/<service-name>"
    echo "  source venv/bin/activate"
    exit 0
elif [ $SUCCESS -gt 0 ]; then
    echo -e "${YELLOW}⚠ 部分服务设置成功${NC}"
    exit 1
else
    echo -e "${RED}✗ 所有服务设置失败${NC}"
    exit 1
fi
