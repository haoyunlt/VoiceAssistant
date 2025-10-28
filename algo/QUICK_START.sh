#!/bin/bash

# 算法服务虚拟环境快速启动脚本
# 快速激活任意服务的虚拟环境

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 显示可用服务
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}算法服务虚拟环境 - 快速启动${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""
echo "可用服务："
echo ""
echo "  1) agent-engine          - Agent 引擎"
echo "  2) indexing-service      - 索引服务"
echo "  3) knowledge-service     - 知识服务"
echo "  4) model-adapter         - 模型适配器"
echo "  5) multimodal-engine     - 多模态引擎"
echo "  6) rag-engine            - RAG 引擎"
echo "  7) retrieval-service     - 检索服务"
echo "  8) vector-store-adapter  - 向量存储适配器"
echo "  9) voice-engine          - 语音引擎"
echo ""

# 如果提供了参数，直接使用
if [ -n "$1" ]; then
    SERVICE=$1
else
    # 交互式选择
    read -p "请选择服务 (1-9 或服务名): " choice

    case $choice in
        1) SERVICE="agent-engine" ;;
        2) SERVICE="indexing-service" ;;
        3) SERVICE="knowledge-service" ;;
        4) SERVICE="model-adapter" ;;
        5) SERVICE="multimodal-engine" ;;
        6) SERVICE="rag-engine" ;;
        7) SERVICE="retrieval-service" ;;
        8) SERVICE="vector-store-adapter" ;;
        9) SERVICE="voice-engine" ;;
        *) SERVICE=$choice ;;
    esac
fi

SERVICE_DIR="$SCRIPT_DIR/$SERVICE"

# 验证服务
if [ ! -d "$SERVICE_DIR" ]; then
    echo -e "${YELLOW}错误: 服务 '$SERVICE' 不存在${NC}"
    exit 1
fi

if [ ! -d "$SERVICE_DIR/venv" ]; then
    echo -e "${YELLOW}警告: 虚拟环境不存在，正在创建...${NC}"
    cd "$SERVICE_DIR"
    python3.11 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
fi

# 显示激活命令
echo ""
echo -e "${GREEN}服务: $SERVICE${NC}"
echo -e "${GREEN}路径: $SERVICE_DIR${NC}"
echo ""
echo -e "${YELLOW}运行以下命令激活虚拟环境:${NC}"
echo ""
echo -e "  ${BLUE}cd $SERVICE_DIR${NC}"
echo -e "  ${BLUE}source venv/bin/activate${NC}"
echo ""
echo "激活后可以："
echo "  • 查看 Python 版本: python --version"
echo "  • 安装依赖: pip install -r requirements.txt"
echo "  • 运行服务: python main.py"
echo "  • 退出虚拟环境: deactivate"
echo ""

# 可选：自动进入目录
read -p "是否自动进入目录? (y/n): " auto_cd
if [ "$auto_cd" = "y" ] || [ "$auto_cd" = "Y" ]; then
    cd "$SERVICE_DIR"
    echo ""
    echo -e "${GREEN}已进入: $(pwd)${NC}"
    echo -e "${YELLOW}请手动运行: source venv/bin/activate${NC}"
    $SHELL
fi
