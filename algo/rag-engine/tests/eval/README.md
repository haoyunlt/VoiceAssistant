# RAG Engine 评测指南

## 概述

本目录包含 RAG Engine 的离线评测脚本和数据集，用于验证优化效果和防止性能回归。

## 目录结构

```
tests/eval/
├── README.md                 # 本文件
├── datasets/                 # 评测数据集
│   ├── general_qa.jsonl     # 通用问答
│   ├── multi_hop.jsonl      # 多跳推理
│   ├── comparison.jsonl     # 对比分析
│   ├── temporal.jsonl       # 时间相关
│   └── domain_specific.jsonl # 领域专用
├── scripts/                  # 评测脚本
│   ├── run_eval.py          # 主评测脚本
│   ├── compute_metrics.py   # 指标计算
│   ├── llm_judge.py         # LLM-as-Judge
│   └── generate_report.py   # 报告生成
├── baselines/                # 基线结果
│   ├── v1.0_baseline.json
│   └── v2.0_target.json
└── results/                  # 评测结果输出
    └── .gitkeep
```

## 数据集格式

### general_qa.jsonl

```jsonl
{
  "id": "qa_001",
  "query": "什么是检索增强生成（RAG）？",
  "ground_truth": "检索增强生成（RAG）是一种结合信息检索和文本生成的AI技术...",
  "relevant_docs": ["doc_123", "doc_456"],
  "difficulty": "easy",
  "category": "simple_fact",
  "metadata": {
    "domain": "ai",
    "language": "zh"
  }
}
```

### multi_hop.jsonl

```jsonl
{
  "id": "mh_001",
  "query": "相比于GPT-3，GPT-4在哪些方面有提升，这些提升对RAG系统有什么影响？",
  "ground_truth": "GPT-4相比GPT-3在推理能力、上下文长度等方面有提升...",
  "reasoning_steps": [
    "找到GPT-4相比GPT-3的改进",
    "分析这些改进与RAG的关系"
  ],
  "required_hops": 2,
  "category": "multi_hop",
  "difficulty": "hard"
}
```

## 运行评测

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements-eval.txt

# 2. 准备数据集（首次运行）
python scripts/prepare_datasets.py

# 3. 运行完整评测
python scripts/run_eval.py \
  --dataset all \
  --output results/$(date +%Y%m%d_%H%M%S).json

# 4. 生成报告
python scripts/generate_report.py \
  --results results/latest.json \
  --baseline baselines/v1.0_baseline.json \
  --output report.html
```

### 评测单个数据集

```bash
# 只评测多跳推理
python scripts/run_eval.py \
  --dataset datasets/multi_hop.jsonl \
  --config ../../configs/rag-engine.yaml \
  --output results/multi_hop_$(date +%Y%m%d).json
```

### 对比两个配置

```bash
# 对比混合检索 vs 纯向量检索
python scripts/run_eval.py \
  --dataset all \
  --config-a configs/hybrid.yaml \
  --config-b configs/vector_only.yaml \
  --output results/ab_test_$(date +%Y%m%d).json
```

## 评测指标

### 检索质量指标

| 指标 | 说明 | 目标值 |
|-----|------|--------|
| **Recall@K** | 前K个结果中相关文档的召回率 | >0.85 @K=5 |
| **Precision@K** | 前K个结果中的精确率 | >0.75 @K=5 |
| **MRR** | 平均倒数排名 | >0.80 |
| **NDCG@K** | 归一化折损累积增益 | >0.80 @K=5 |

### 答案质量指标

| 指标 | 说明 | 计算方式 |
|-----|------|---------|
| **Answer Accuracy** | 答案正确率 | 人工标注 + LLM Judge |
| **ROUGE-L** | 与参考答案的重叠度 | Rouge Score |
| **BLEU** | 生成质量 | BLEU Score |
| **Hallucination Rate** | 幻觉率（答案与检索文档不一致） | NLI模型检测 |
| **Citation Accuracy** | 引用准确率 | 引用来源是否正确 |

### 性能指标

| 指标 | 说明 | 目标值 |
|-----|------|--------|
| **E2E Latency** | 端到端延迟（P95） | <2.5s |
| **Retrieval Latency** | 检索延迟（P95） | <500ms |
| **Token Usage** | 平均Token消耗 | <2000 |

## LLM-as-Judge 评测

使用 GPT-4 作为评判模型，评估答案质量：

```bash
python scripts/llm_judge.py \
  --results results/latest.json \
  --judge-model gpt-4-turbo-preview \
  --criteria relevance correctness completeness \
  --output results/latest_judged.json
```

### Judge Prompt 示例

```
请评估以下RAG系统生成的答案：

【问题】
{query}

【检索到的文档】
{retrieved_docs}

【生成的答案】
{answer}

【参考答案】（可选）
{ground_truth}

请从以下维度打分（1-5分）：
1. 相关性（Relevance）：答案是否直接回答了问题
2. 正确性（Correctness）：答案是否基于检索文档，无捏造内容
3. 完整性（Completeness）：答案是否全面
4. 引用准确性（Citation）：引用的来源是否正确

返回JSON格式：
{
  "relevance": 5,
  "correctness": 4,
  "completeness": 4,
  "citation": 5,
  "reasoning": "答案准确且完整，但可以更简洁..."
}
```

## 基线对比

### v1.0 基线（当前）

```json
{
  "version": "1.0.0",
  "date": "2025-01-15",
  "metrics": {
    "recall_at_5": 0.68,
    "precision_at_5": 0.72,
    "mrr": 0.75,
    "answer_accuracy": 0.71,
    "hallucination_rate": 0.15,
    "e2e_latency_p95_ms": 3200,
    "token_usage_avg": 2450
  },
  "config": {
    "retrieval": "vector_only",
    "reranking": false,
    "cache": "basic"
  }
}
```

### v2.0 目标（优化后）

```json
{
  "version": "2.0.0",
  "date": "2025-04-30",
  "metrics": {
    "recall_at_5": 0.87,        // +27%
    "precision_at_5": 0.78,     // +8%
    "mrr": 0.84,                // +12%
    "answer_accuracy": 0.92,    // +30%
    "hallucination_rate": 0.05, // -67%
    "e2e_latency_p95_ms": 2300, // -28%
    "token_usage_avg": 1850     // -24%
  },
  "config": {
    "retrieval": "hybrid_graph",
    "reranking": true,
    "cache": "semantic_faiss",
    "self_rag": true,
    "compression": true
  }
}
```

## 持续集成

### GitHub Actions 自动评测

```yaml
# .github/workflows/rag-eval.yml
name: RAG Evaluation

on:
  pull_request:
    paths:
      - 'algo/rag-engine/**'
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          cd algo/rag-engine
          pip install -r requirements.txt
          pip install -r tests/eval/requirements-eval.txt

      - name: Run evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          cd algo/rag-engine/tests/eval
          python scripts/run_eval.py --dataset all --output results/ci_${{ github.run_id }}.json

      - name: Compare with baseline
        run: |
          python scripts/compare_baseline.py \
            --current results/ci_${{ github.run_id }}.json \
            --baseline baselines/v1.0_baseline.json \
            --threshold 0.95  # 不允许指标下降超过5%

      - name: Generate report
        if: always()
        run: |
          python scripts/generate_report.py \
            --results results/ci_${{ github.run_id }}.json \
            --output report.html

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: eval-report
          path: report.html
```

## 人工评测

对于主观质量评测，需要人工标注：

```bash
# 1. 导出待评测样本
python scripts/export_for_annotation.py \
  --results results/latest.json \
  --sample-size 50 \
  --output annotations/batch_001.csv

# 2. 人工标注（Excel编辑）

# 3. 导入标注结果
python scripts/import_annotations.py \
  --input annotations/batch_001_annotated.csv \
  --results results/latest.json \
  --output results/latest_with_human_eval.json
```

## 故障排查

### 评测失败常见原因

1. **检索服务不可达**
   ```bash
   # 检查服务状态
   curl http://localhost:8006/health
   ```

2. **API密钥未设置**
   ```bash
   export OPENAI_API_KEY="your-key"
   ```

3. **数据集格式错误**
   ```bash
   # 验证数据集
   python scripts/validate_dataset.py datasets/general_qa.jsonl
   ```

## 性能分析

### 生成延迟分析报告

```bash
python scripts/analyze_latency.py \
  --results results/latest.json \
  --output latency_breakdown.png
```

输出：
- 各阶段耗时占比（饼图）
- 延迟分布（直方图）
- P50/P95/P99 数值

### 成本分析报告

```bash
python scripts/analyze_cost.py \
  --results results/latest.json \
  --pricing configs/pricing.json \
  --output cost_analysis.html
```

## 最佳实践

1. **每次迭代前建立基线**
   ```bash
   python scripts/run_eval.py --dataset all --output baselines/iter_X_baseline.json
   ```

2. **A/B 测试验证优化效果**
   - 至少运行 100+ 样本
   - 统计显著性检验（t-test）

3. **定期更新数据集**
   - 从生产日志中提取真实 badcase
   - 覆盖各类场景

4. **可视化指标趋势**
   ```bash
   python scripts/plot_metrics_trend.py \
     --results-dir results/ \
     --output metrics_trend.html
   ```

## 相关文档

- [RAG Engine 优化迭代计划](../../../docs/RAG_ENGINE_ITERATION_PLAN.md)
- [架构设计文档](../../../docs/arch/overview.md)
- [Runbook](../../../docs/runbook/index.md)

## 联系方式

- **负责人**: [指定]
- **Slack**: #rag-optimization
- **Issue Template**: [RAG Evaluation Issue](https://github.com/xxx/issues/new?template=rag_eval.md)
