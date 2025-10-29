# RAG 评测框架

## 目录结构

```
tests/eval/
├── README.md                    # 本文件
├── retrieval/                   # 检索评测
│   ├── test_retrieval.py
│   ├── test_bm25.py
│   ├── test_hybrid.py
│   └── datasets/
│       ├── ms_marco_subset.json
│       └── custom_qa_pairs.json
├── rerank/                      # 重排序评测
│   ├── test_cross_encoder.py
│   ├── test_llm_rerank.py
│   └── datasets/
│       └── rerank_pairs.json
├── compression/                 # 压缩评测
│   ├── test_semantic_compression.py
│   ├── test_keyword_compression.py
│   └── datasets/
│       └── long_documents.json
├── e2e/                        # 端到端评测
│   ├── test_rag_pipeline.py
│   ├── test_qa_quality.py
│   └── datasets/
│       ├── qa_pairs.json
│       └── golden_answers.json
├── scripts/                    # 评测脚本
│   ├── run_all_evals.sh
│   ├── generate_baseline.py
│   └── compare_metrics.py
└── reports/                    # 评测报告（CI 生成）
    ├── baseline_v1.json
    └── latest_run.json
```

---

## 评测指标

### 1. 检索评测 (Retrieval)

| 指标 | 目标 | 说明 |
|------|------|------|
| Recall@5 | ≥0.85 | 前5个结果中包含相关文档的比例 |
| Recall@10 | ≥0.90 | 前10个结果中包含相关文档的比例 |
| MRR (Mean Reciprocal Rank) | ≥0.75 | 第一个相关结果的倒数排名均值 |
| Latency P95 | <500ms | 95分位延迟 |

### 2. 重排序评测 (Reranking)

| 指标 | 目标 | 说明 |
|------|------|------|
| NDCG@5 | ≥0.90 | 归一化折损累积增益 |
| MAP (Mean Average Precision) | ≥0.85 | 平均精度均值 |
| Latency P95 | <2000ms | 95分位延迟 |

### 3. 压缩评测 (Compression)

| 指标 | 目标 | 说明 |
|------|------|------|
| Compression Ratio | 0.4-0.6 | 压缩率（1-压缩后长度/原始长度）|
| Information Retention | ≥0.90 | 信息保留率（ROUGE-L） |
| Latency P95 | <200ms | 95分位延迟 |

### 4. 端到端评测 (E2E)

| 指标 | 目标 | 说明 |
|------|------|------|
| Answer Accuracy | ≥0.80 | 答案准确性（人工标注或GPT评分）|
| Faithfulness | ≥0.85 | 答案忠实度（基于检索内容）|
| Relevance | ≥0.85 | 答案相关性 |
| Latency P95 | <2500ms | 端到端延迟 |

---

## 快速开始

### 1. 安装依赖

```bash
cd tests/eval
pip install -r requirements.txt
```

### 2. 准备数据集

```bash
# 下载 MS MARCO 子集
python scripts/download_datasets.py

# 或使用自定义数据集
cp your_dataset.json retrieval/datasets/custom_qa_pairs.json
```

### 3. 运行评测

```bash
# 运行所有评测
bash scripts/run_all_evals.sh

# 运行单个模块
pytest retrieval/test_retrieval.py -v
pytest rerank/test_cross_encoder.py -v
pytest e2e/test_rag_pipeline.py -v
```

### 4. 查看报告

```bash
# 生成基线
python scripts/generate_baseline.py --output reports/baseline_v1.json

# 对比最新运行与基线
python scripts/compare_metrics.py \
    --baseline reports/baseline_v1.json \
    --current reports/latest_run.json
```

---

## 数据集格式

### 检索数据集 (retrieval)

```json
{
  "queries": [
    {
      "query_id": "q1",
      "query": "什么是 RAG?",
      "relevant_docs": ["doc_123", "doc_456"]
    }
  ],
  "documents": [
    {
      "doc_id": "doc_123",
      "content": "RAG (Retrieval-Augmented Generation) 是..."
    }
  ]
}
```

### 重排序数据集 (rerank)

```json
{
  "pairs": [
    {
      "query": "什么是 RAG?",
      "doc_id": "doc_123",
      "relevance_score": 2
    }
  ]
}
```

### 端到端数据集 (e2e)

```json
{
  "qa_pairs": [
    {
      "question": "什么是 RAG?",
      "golden_answer": "RAG 是一种结合检索和生成的技术...",
      "context_docs": ["doc_123"],
      "metadata": {
        "difficulty": "easy",
        "category": "definition"
      }
    }
  ]
}
```

---

## CI 集成

### GitHub Actions 配置

```yaml
name: RAG Evaluation

on:
  pull_request:
    paths:
      - 'algo/retrieval-service/**'
      - 'algo/rag-engine/**'
      - 'tests/eval/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd tests/eval
          pip install -r requirements.txt
      
      - name: Run evaluations
        run: |
          bash tests/eval/scripts/run_all_evals.sh
      
      - name: Compare with baseline
        run: |
          python tests/eval/scripts/compare_metrics.py \
            --baseline tests/eval/reports/baseline_v1.json \
            --current tests/eval/reports/latest_run.json \
            --threshold 0.05
      
      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: eval-report
          path: tests/eval/reports/latest_run.json
```

---

## 评测最佳实践

### 1. 数据集设计
- ✅ 覆盖多种查询类型（事实、定义、how-to、why）
- ✅ 包含简单和复杂查询
- ✅ 定期更新数据集
- ✅ 人工审核标注质量

### 2. 指标选择
- ✅ 检索：Recall + MRR（召回为主）
- ✅ 重排序：NDCG + MAP（排序质量）
- ✅ 端到端：Accuracy + Faithfulness（生成质量）

### 3. 基线管理
- ✅ 每次重大变更建立新基线
- ✅ 保留历史基线用于回归测试
- ✅ 定期重新评估基线合理性

### 4. CI 门禁
- ✅ 核心指标下降 >5% 则 PR 失败
- ✅ 延迟增加 >20% 则发出警告
- ✅ 生成对比报告附在 PR 评论中

---

## 常见问题

### Q: 如何添加自定义指标？

在 `scripts/metrics.py` 中添加新指标函数：

```python
def my_custom_metric(predictions, ground_truth):
    # 实现逻辑
    return score
```

### Q: 如何使用 GPU 加速评测？

设置环境变量：

```bash
export CUDA_VISIBLE_DEVICES=0
pytest retrieval/test_retrieval.py
```

### Q: 评测数据集保密怎么办？

将数据集加密存储：

```bash
# 加密
openssl enc -aes-256-cbc -salt -in dataset.json -out dataset.json.enc

# 解密（CI 中）
openssl enc -d -aes-256-cbc -in dataset.json.enc -out dataset.json
```

---

## 贡献指南

添加新评测时，请确保：

1. 遵循现有目录结构
2. 包含至少 10 个测试样例
3. 文档化评测目的和预期结果
4. 更新本 README

---

## 参考资料

- [MS MARCO 数据集](https://microsoft.github.io/msmarco/)
- [BEIR 基准测试](https://github.com/beir-cellar/beir)
- [RAG 评测最佳实践](https://arxiv.org/abs/2404.10981)

