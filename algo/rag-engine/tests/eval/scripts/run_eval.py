#!/usr/bin/env python3
"""
RAG Engine 评测脚本

用法:
    python run_eval.py --dataset all --output results/$(date +%Y%m%d).json
    python run_eval.py --dataset datasets/multi_hop.jsonl --config configs/hybrid.yaml
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from tqdm import tqdm

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RAGEvaluator:
    """RAG 评测器"""

    def __init__(self, rag_endpoint: str = "http://localhost:8006", timeout: float = 30.0):
        """
        初始化评测器

        Args:
            rag_endpoint: RAG Engine 服务地址
            timeout: 请求超时时间（秒）
        """
        self.rag_endpoint = rag_endpoint
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def load_dataset(self, dataset_path: str) -> list[dict[str, Any]]:
        """加载评测数据集"""
        logger.info(f"Loading dataset from {dataset_path}")

        dataset = []
        with open(dataset_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    dataset.append(json.loads(line))

        logger.info(f"Loaded {len(dataset)} test cases")
        return dataset

    async def evaluate_query(self, query: str, _test_case: dict[str, Any]) -> dict[str, Any]:
        """评测单个查询"""
        start_time = time.time()

        try:
            # 调用 RAG Engine
            response = await self.client.post(
                f"{self.rag_endpoint}/api/v1/rag/query",
                json={
                    "query": query,
                    "tenant_id": "test_tenant",
                    "mode": "advanced",
                    "include_sources": True,
                },
            )
            response.raise_for_status()
            result = response.json()

            latency = (time.time() - start_time) * 1000  # ms

            # 提取结果
            return {
                "success": True,
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "retrieved_count": result.get("retrieved_count", 0),
                "latency_ms": latency,
                "rewritten_query": result.get("rewritten_query", ""),
                "error": None,
            }

        except Exception as e:
            logger.error(f"Error evaluating query '{query}': {e}")
            return {
                "success": False,
                "answer": "",
                "sources": [],
                "retrieved_count": 0,
                "latency_ms": 0,
                "error": str(e),
            }

    async def compute_metrics(
        self, test_case: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, float]:
        """计算评测指标"""
        metrics = {}

        # 1. 检索指标
        relevant_docs = set(test_case.get("relevant_docs", []))
        retrieved_docs = {src.get("document_id") for src in result.get("sources", [])}

        if relevant_docs:
            # Recall@K
            intersection = relevant_docs & retrieved_docs
            metrics["recall_at_k"] = len(intersection) / len(relevant_docs)

            # Precision@K
            if retrieved_docs:
                metrics["precision_at_k"] = len(intersection) / len(retrieved_docs)
            else:
                metrics["precision_at_k"] = 0.0
        else:
            metrics["recall_at_k"] = 0.0
            metrics["precision_at_k"] = 0.0

        # 2. 答案质量（简化版，使用 ROUGE-L）
        from rouge import Rouge

        rouge = Rouge()

        ground_truth = test_case.get("ground_truth", "")
        answer = result.get("answer", "")

        if ground_truth and answer:
            try:
                scores = rouge.get_scores(answer, ground_truth, avg=True)
                metrics["rouge_l_f1"] = scores["rouge-l"]["f"]
            except Exception as e:
                logger.warning(f"Error computing ROUGE: {e}")
                metrics["rouge_l_f1"] = 0.0
        else:
            metrics["rouge_l_f1"] = 0.0

        # 3. 性能指标
        metrics["latency_ms"] = result.get("latency_ms", 0)

        # 4. 成功率
        metrics["success"] = 1.0 if result.get("success") else 0.0

        return metrics

    async def run_evaluation(
        self, dataset: list[dict[str, Any]], progress_bar: bool = True
    ) -> dict[str, Any]:
        """运行完整评测"""
        logger.info(f"Starting evaluation on {len(dataset)} test cases")

        results = []
        all_metrics = []

        # 使用 tqdm 显示进度
        iterator = tqdm(dataset, desc="Evaluating") if progress_bar else dataset

        for test_case in iterator:
            query = test_case.get("query", "")
            test_id = test_case.get("id", "")

            # 评测查询
            result = await self.evaluate_query(query, test_case)

            # 计算指标
            metrics = await self.compute_metrics(test_case, result)

            # 保存结果
            results.append(
                {
                    "test_id": test_id,
                    "query": query,
                    "category": test_case.get("category", "unknown"),
                    "difficulty": test_case.get("difficulty", "medium"),
                    "result": result,
                    "metrics": metrics,
                }
            )

            all_metrics.append(metrics)

        # 汇总指标
        summary = self._aggregate_metrics(all_metrics)

        return {
            "summary": summary,
            "results": results,
            "total_cases": len(dataset),
            "timestamp": time.time(),
        }

    def _aggregate_metrics(self, all_metrics: list[dict[str, float]]) -> dict[str, Any]:
        """汇总指标"""
        if not all_metrics:
            return {}

        summary = {}

        # 计算各指标的平均值
        metric_names = all_metrics[0].keys()
        for metric_name in metric_names:
            values = [m[metric_name] for m in all_metrics]
            summary[f"{metric_name}_mean"] = sum(values) / len(values)

            # 计算中位数和百分位
            sorted_values = sorted(values)
            n = len(sorted_values)
            summary[f"{metric_name}_median"] = sorted_values[n // 2]

            if metric_name == "latency_ms":
                summary[f"{metric_name}_p95"] = sorted_values[int(n * 0.95)]
                summary[f"{metric_name}_p99"] = sorted_values[int(n * 0.99)]

        # 成功率
        success_count = sum(1 for m in all_metrics if m.get("success", 0) == 1.0)
        summary["success_rate"] = success_count / len(all_metrics)

        return summary

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="RAG Engine 评测脚本")

    parser.add_argument(
        "--dataset", type=str, required=True, help="数据集路径 (或 'all' 评测所有数据集)"
    )
    parser.add_argument("--output", type=str, required=True, help="输出结果路径 (JSON 格式)")
    parser.add_argument(
        "--endpoint", type=str, default="http://localhost:8006", help="RAG Engine 服务地址"
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="请求超时时间（秒）")
    parser.add_argument("--config", type=str, help="RAG Engine 配置文件路径（可选）")

    args = parser.parse_args()

    # 创建评测器
    evaluator = RAGEvaluator(rag_endpoint=args.endpoint, timeout=args.timeout)

    try:
        # 加载数据集
        if args.dataset == "all":
            # 加载所有数据集
            dataset_dir = Path(__file__).parent.parent / "datasets"
            datasets = list(dataset_dir.glob("*.jsonl"))
            logger.info(f"Found {len(datasets)} datasets")

            all_results = {}
            for dataset_path in datasets:
                dataset_name = dataset_path.stem
                logger.info(f"\n{'=' * 60}")
                logger.info(f"Evaluating dataset: {dataset_name}")
                logger.info(f"{'=' * 60}")

                dataset = await evaluator.load_dataset(str(dataset_path))
                results = await evaluator.run_evaluation(dataset)
                all_results[dataset_name] = results

            final_results = {"datasets": all_results, "timestamp": time.time()}
        else:
            # 单个数据集
            dataset = await evaluator.load_dataset(args.dataset)
            final_results = await evaluator.run_evaluation(dataset)

        # 保存结果
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Evaluation complete! Results saved to {output_path}")
        logger.info(f"{'=' * 60}")

        # 打印摘要
        if "summary" in final_results:
            summary = final_results["summary"]
            logger.info("\n📊 Evaluation Summary:")
            logger.info(f"  - Success Rate: {summary.get('success_rate_mean', 0):.2%}")
            logger.info(f"  - Recall@K: {summary.get('recall_at_k_mean', 0):.2%}")
            logger.info(f"  - Precision@K: {summary.get('precision_at_k_mean', 0):.2%}")
            logger.info(f"  - ROUGE-L F1: {summary.get('rouge_l_f1_mean', 0):.3f}")
            logger.info(f"  - Latency P95: {summary.get('latency_ms_p95', 0):.0f} ms")

    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        await evaluator.close()


if __name__ == "__main__":
    asyncio.run(main())
