#!/bin/bash

# Voice Engine 快速启动脚本
# 用途: 快速启动 Voice Engine 并测试流式 ASR

set -e

echo "🚀 Voice Engine 快速启动"
echo "===================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  虚拟环境不存在，正在创建...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 安装/更新依赖
echo ""
echo "检查依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo -e "${GREEN}✅ 依赖检查完成${NC}"

# 检查模型
echo ""
echo "检查 Whisper 模型..."
if [ ! -d "$HOME/.cache/huggingface/hub" ]; then
    echo "首次运行，正在下载 Whisper base 模型..."
    python3 << EOF
from faster_whisper import WhisperModel
print("正在下载模型...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("✅ 模型下载完成")
EOF
else
    echo -e "${GREEN}✅ Whisper 模型已存在${NC}"
fi

# 创建 static 目录
if [ ! -d "static" ]; then
    mkdir -p static
    echo -e "${GREEN}✅ static 目录已创建${NC}"
fi

# 启动服务
echo ""
echo "===================================="
echo "🚀 启动 Voice Engine..."
echo "===================================="
echo ""
echo "服务端口: 8001"
echo "API 文档: http://localhost:8001/docs"
echo "测试页面: http://localhost:8001/static/test_streaming_asr.html"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8001
