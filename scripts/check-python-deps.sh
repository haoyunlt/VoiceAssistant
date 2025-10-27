#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> 检查 Python 服务依赖"

PYTHON_SERVICES=(
    "agent-engine"
    "rag-engine"
    "indexing-service"
    "retrieval-service"
    "voice-engine"
    "multimodal-engine"
    "model-adapter"
    "vector-store-adapter"
    "knowledge-service"
)

for service in "${PYTHON_SERVICES[@]}"; do
    service_path="${PROJECT_ROOT}/algo/${service}"
    if [ -f "${service_path}/requirements.txt" ]; then
        echo "  ✓ ${service}: requirements.txt 存在"
        echo "    依赖数量: $(wc -l < "${service_path}/requirements.txt" | tr -d ' ')"
    else
        echo "  ✗ ${service}: requirements.txt 缺失"
    fi
done

echo ""
echo "提示：要安装所有依赖，请运行："
echo "  cd algo/<service-name> && pip install -r requirements.txt"
echo "  或使用虚拟环境："
echo "  cd algo/<service-name> && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
