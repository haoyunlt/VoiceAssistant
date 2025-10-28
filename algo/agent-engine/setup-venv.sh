#!/bin/bash

# Agent Engine 虚拟环境设置脚本
# Python 3.11

set -e

echo "Setting up Agent Engine virtual environment..."

# 检查 Python 3.11 是否安装
if ! command -v python3.11 &> /dev/null; then
    echo "Error: Python 3.11 is not installed."
    echo "Please install Python 3.11 first."
    exit 1
fi

# 创建虚拟环境
echo "Creating virtual environment..."
python3.11 -m venv venv

# 激活虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

# 升级 pip（使用清华镜像源）
echo "Upgrading pip..."
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

# 安装依赖（使用清华镜像源）
echo "Installing dependencies from Tsinghua mirror..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "Virtual environment setup complete!"
echo "To activate the virtual environment, run: source venv/bin/activate"
