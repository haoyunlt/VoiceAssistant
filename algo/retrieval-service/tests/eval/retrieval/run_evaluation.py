#!/usr/bin/env python3
"""
Retrieval Evaluation Suite - 检索评测套件

功能:
- 评测检索系统的质量指标
- 支持多种评测指标
- 对比不同策略的效果

评测指标:
- Recall@K: 召回率
- Precision@K: 精确率
- MRR (Mean Reciprocal Rank): 平均倒数排名
- NDCG@K: 归一化折损累计增益
- Latency: 延迟
"""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class EvalDataPoint:
    """评测数据点"""

    query_id: str
    query: str
    relevant_doc_ids: list[str]  # 相关文档ID列表


@dataclass
class RetrievalResult:
    """检索结果"""

    query_id: str
    retrieved_doc_ids: list[str]
    scores: list[float]
    latency_ms: float


@dataclass
class EvalMetrics:
    """评测指标"""

    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


class RetrievalEvaluator:
    """检索评测器"""

    def __init__(self, data_path: str):
        """
        初始化评测器

        Args:
            data_path: 评测数据路径
        """
        self.data_path = data_path
        self.eval_data: list[EvalDataPoint] = []
        self._load_data()

    def _load_data(self):
        """加载评测数据"""
        data_file = Path(self.data_path)

        if not data_file.exists():
            print(f"⚠️  评测数据不存在: {data_file}")
            print("创建示例数据...")
            self._create_sample_data()
            return

        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            self.eval_data.append(
                EvalDataPoint(
                    query_id=item["query_id"],
                    query=item["query"],
                    relevant_doc_ids=item["relevant_doc_ids"],
                )
            )

        print(f"✅ 加载评测数据: {len(self.eval_data)}条")

    def _create_sample_data(self):
        """创建示例数据"""
        sample_data = [
            {
                "query_id": "q1",
                "query": "如何使用Python",
                "relevant_doc_ids": ["doc1", "doc2", "doc5"],
            },
            {
                "query_id": "q2",
                "query": "什么是机器学习",
                "relevant_doc_ids": ["doc3", "doc7"],
            },
            {
                "query_id": "q3",
                "query": "数据分析最佳实践",
                "relevant_doc_ids": ["doc4", "doc6", "doc8", "doc10"],
            },
        ]

        for item in sample_data:
            self.eval_data.append(
                EvalDataPoint(
                    query_id=item["query_id"],
                    query=item["query"],
                    relevant_doc_ids=item["relevant_doc_ids"],
                )
            )

        # 保存示例数据
        Path(self.data_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 创建示例数据: {len(self.eval_data)}条")

    def calculate_metrics(self, results: list[RetrievalResult]) -> EvalMetrics:
        """
        计算评测指标

        Args:
            results: 检索结果列表

        Returns:
            评测指标
        """
        # 将结果转为字典
        result_dict = {r.query_id: r for r in results}

        # 计算各项指标
        recall_5_list = []
        recall_10_list = []
        recall_20_list = []
        precision_5_list = []
        precision_10_list = []
        mrr_list = []
        ndcg_10_list = []
        latencies = []

        for data_point in self.eval_data:
            if data_point.query_id not in result_dict:
                continue

            result = result_dict[data_point.query_id]
            relevant = set(data_point.relevant_doc_ids)

            # Recall@K
            recall_5_list.append(self._recall_at_k(result.retrieved_doc_ids, relevant, 5))
            recall_10_list.append(self._recall_at_k(result.retrieved_doc_ids, relevant, 10))
            recall_20_list.append(self._recall_at_k(result.retrieved_doc_ids, relevant, 20))

            # Precision@K
            precision_5_list.append(self._precision_at_k(result.retrieved_doc_ids, relevant, 5))
            precision_10_list.append(self._precision_at_k(result.retrieved_doc_ids, relevant, 10))

            # MRR
            mrr_list.append(self._mrr(result.retrieved_doc_ids, relevant))

            # NDCG@10
            ndcg_10_list.append(self._ndcg_at_k(result.retrieved_doc_ids, relevant, 10))

            # Latency
            latencies.append(result.latency_ms)

        # 汇总
        metrics = EvalMetrics(
            recall_at_5=sum(recall_5_list) / len(recall_5_list) if recall_5_list else 0,
            recall_at_10=sum(recall_10_list) / len(recall_10_list) if recall_10_list else 0,
            recall_at_20=sum(recall_20_list) / len(recall_20_list) if recall_20_list else 0,
            precision_at_5=sum(precision_5_list) / len(precision_5_list) if precision_5_list else 0,
            precision_at_10=sum(precision_10_list) / len(precision_10_list)
            if precision_10_list
            else 0,
            mrr=sum(mrr_list) / len(mrr_list) if mrr_list else 0,
            ndcg_at_10=sum(ndcg_10_list) / len(ndcg_10_list) if ndcg_10_list else 0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            p95_latency_ms=sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            p99_latency_ms=sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
        )

        return metrics

    def _recall_at_k(self, retrieved: list[str], relevant: set, k: int) -> float:
        """计算Recall@K"""
        if not relevant:
            return 0.0

        retrieved_at_k = set(retrieved[:k])
        hits = len(retrieved_at_k & relevant)
        return hits / len(relevant)

    def _precision_at_k(self, retrieved: list[str], relevant: set, k: int) -> float:
        """计算Precision@K"""
        retrieved_at_k = retrieved[:k]
        if not retrieved_at_k:
            return 0.0

        hits = sum(1 for doc_id in retrieved_at_k if doc_id in relevant)
        return hits / len(retrieved_at_k)

    def _mrr(self, retrieved: list[str], relevant: set) -> float:
        """计算MRR (Mean Reciprocal Rank)"""
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                return 1.0 / i
        return 0.0

    def _ndcg_at_k(self, retrieved: list[str], relevant: set, k: int) -> float:
        """计算NDCG@K"""
        # 简化的NDCG计算：假设相关文档权重为1，不相关为0
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k], 1):
            if doc_id in relevant:
                dcg += 1.0 / (i if i == 1 else (i * 0.693))  # log2(i+1)

        # Ideal DCG
        idcg = 0.0
        for i in range(1, min(len(relevant), k) + 1):
            idcg += 1.0 / (i if i == 1 else (i * 0.693))

        return dcg / idcg if idcg > 0 else 0.0


async def run_evaluation(strategy: str, _config_path: str | None = None):
    """
    运行评测

    Args:
        strategy: 策略名称 (baseline, expansion, hyde, etc.)
        config_path: 配置文件路径
    """
    print("\n" + "=" * 70)
    print(f"Retrieval Evaluation - Strategy: {strategy}")
    print("=" * 70 + "\n")

    # 加载评测数据
    data_path = "tests/eval/retrieval/datasets/eval_data.json"
    evaluator = RetrievalEvaluator(data_path)

    if not evaluator.eval_data:
        print("❌ 没有评测数据")
        return

    # 模拟检索结果（实际应该调用retrieval API）
    results = []
    for data_point in evaluator.eval_data:
        # 这里需要实际调用检索服务
        # 暂时模拟结果
        await asyncio.sleep(0.01)  # 模拟网络延迟

        # 模拟检索结果
        retrieved_docs = [f"doc{i}" for i in range(1, 11)]
        scores = [0.9 - i * 0.05 for i in range(10)]

        results.append(
            RetrievalResult(
                query_id=data_point.query_id,
                retrieved_doc_ids=retrieved_docs,
                scores=scores,
                latency_ms=150.0,
            )
        )

    # 计算指标
    metrics = evaluator.calculate_metrics(results)

    # 输出结果
    print(f"评测结果 ({len(results)}条查询):\n")
    print("  召回率:")
    print(f"    Recall@5:  {metrics.recall_at_5:.3f}")
    print(f"    Recall@10: {metrics.recall_at_10:.3f}")
    print(f"    Recall@20: {metrics.recall_at_20:.3f}")
    print("\n  精确率:")
    print(f"    Precision@5:  {metrics.precision_at_5:.3f}")
    print(f"    Precision@10: {metrics.precision_at_10:.3f}")
    print("\n  排序质量:")
    print(f"    MRR:       {metrics.mrr:.3f}")
    print(f"    NDCG@10:   {metrics.ndcg_at_10:.3f}")
    print("\n  性能:")
    print(f"    平均延迟:  {metrics.avg_latency_ms:.1f}ms")
    print(f"    P95延迟:   {metrics.p95_latency_ms:.1f}ms")
    print(f"    P99延迟:   {metrics.p99_latency_ms:.1f}ms")

    # 保存结果
    result_file = f"tests/eval/retrieval/results/{strategy}_results.json"
    Path(result_file).parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(asdict(metrics), f, ensure_ascii=False, indent=2)

    print(f"\n✅ 结果已保存: {result_file}\n")


def main():
    parser = argparse.ArgumentParser(description="检索系统评测")
    parser.add_argument(
        "--strategy",
        type=str,
        default="baseline",
        help="评测策略 (baseline, expansion, hyde, etc.)",
    )
    parser.add_argument("--config", type=str, help="配置文件路径")

    args = parser.parse_args()

    asyncio.run(run_evaluation(args.strategy, args.config))


if __name__ == "__main__":
    main()
