#!/usr/bin/env bash
# 下载评测数据集

set -euo pipefail

DATASETS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/datasets"

echo "下载评测数据集到: $DATASETS_DIR"

# MS MARCO Dev Small (1000 queries)
if [ ! -f "$DATASETS_DIR/ms_marco_dev_small.jsonl" ]; then
    echo "下载 MS MARCO Dev Small..."
    # TODO: 替换为实际下载链接
    # wget https://example.com/ms_marco_dev_small.jsonl.gz -O "$DATASETS_DIR/ms_marco_dev_small.jsonl.gz"
    # gunzip "$DATASETS_DIR/ms_marco_dev_small.jsonl.gz"
    echo "⚠️  需要手动下载 MS MARCO 数据集"
else
    echo "✓ MS MARCO 数据集已存在"
fi

# Natural Questions (可选)
if [ ! -f "$DATASETS_DIR/natural_questions.jsonl" ]; then
    echo "下载 Natural Questions..."
    # TODO: 下载链接
    echo "⚠️  需要手动下载 Natural Questions 数据集"
else
    echo "✓ Natural Questions 数据集已存在"
fi

echo "数据集准备完成"
