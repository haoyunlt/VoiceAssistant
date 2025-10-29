# Retrieval Service 评测

## 快速开始

### 1. 下载数据集

```bash
./download_datasets.sh
```

### 2. 运行Baseline评测

```bash
python run_evaluation.py --baseline --config config.yaml
```

### 3. 评测新策略

```bash
python run_evaluation.py --strategy hybrid_rerank --compare-with baseline
```

### 4. 查看报告

```bash
open reports/eval_latest.html
```

## 评测指标

- **MRR@10**: Mean Reciprocal Rank at 10
- **NDCG@10**: Normalized Discounted Cumulative Gain at 10
- **Recall@K**: 召回率
- **Precision@K**: 精确率

## 添加自定义数据集

编辑 `config.yaml`:

```yaml
datasets:
  - name: "my_dataset"
    path: "datasets/my_dataset.jsonl"
    format: "jsonl"
    fields:
      query: "query"
      doc_id: "doc_id"
      relevance: "label"
```

数据格式:
```json
{"query": "如何使用Python", "doc_id": "doc_123", "label": 1}
```
