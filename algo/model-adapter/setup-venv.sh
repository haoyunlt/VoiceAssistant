#!/bin/bash

# Model Adapter 虚拟环境设置脚本
# Python 3.11

set -e

echo "Setting up Model Adapter virtual environment..."

if ! command -v python3.11 &> /dev/null; then
    echo "Error: Python 3.11 is not installed."
    echo "Please install Python 3.11 first."
    exit 1
fi

echo "Creating virtual environment..."
python3.11 -m venv venv

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "Installing dependencies from Tsinghua mirror..."
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo "Virtual environment setup complete!"
echo "To activate the virtual environment, run: source venv/bin/activate"
