"""
成本优化器集成示例

展示如何将成本优化器集成到实际的文档处理流程中
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 模拟依赖
class MockEmbedder:
    """模拟 Embedder"""

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """模拟向量化"""
        # 返回模拟向量
        return [[0.1, 0.2, 0.3] * 256 for _ in texts]

    def get_dimension(self) -> int:
        return 768


class DocumentProcessorWithCostOptimization:
    """集成成本优化的文档处理器"""

    def __init__(
        self,
        enable_deduplication: bool = True,
        enable_caching: bool = True,
        daily_budget: float = 100.0,
        monthly_budget: float = 3000.0,
    ):
        """
        初始化文档处理器

        Args:
            enable_deduplication: 是否启用去重
            enable_caching: 是否启用缓存
            daily_budget: 每日预算
            monthly_budget: 每月预算
        """
        from app.core.cost_optimizer import CostBudgetManager, CostOptimizer

        # 初始化组件
        self.embedder = MockEmbedder()

        # 成本优化器
        self.cost_optimizer = CostOptimizer(
            model_name="bge-m3",
            enable_deduplication=enable_deduplication,
        )

        # 预算管理器
        self.budget_manager = CostBudgetManager(
            daily_budget=daily_budget,
            monthly_budget=monthly_budget,
            alert_threshold=0.8,
        )

        self.enable_caching = enable_caching

        logger.info(
            f"DocumentProcessor initialized: "
            f"dedup={enable_deduplication}, cache={enable_caching}, "
            f"budget=${daily_budget}/day, ${monthly_budget}/month"
        )

    async def process_document(
        self, document: Dict[str, Any], tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        处理单个文档

        Args:
            document: 文档信息（包含分块）
            tenant_id: 租户 ID

        Returns:
            处理结果（包含向量和统计）
        """
        doc_id = document.get("id", "unknown")
        chunks = document.get("chunks", [])

        logger.info(f"Processing document {doc_id}: {len(chunks)} chunks")

        # 提取文本
        texts = [chunk["content"] for chunk in chunks]

        # 1. 预算检查
        estimated_tokens = sum(self.cost_optimizer.token_counter.count_tokens(t) for t in texts)
        estimated_cost = self.cost_optimizer.token_counter.estimate_cost(estimated_tokens, "bge-m3")

        can_proceed, message = self.budget_manager.check_budget(estimated_cost)
        if not can_proceed:
            logger.error(f"Budget check failed: {message}")
            raise RuntimeError(f"Budget exceeded: {message}")

        # 2. 成本优化（去重）
        unique_texts, indices, opt_stats = self.cost_optimizer.optimize_and_calculate(
            texts=texts, model="bge-m3", tenant_id=tenant_id
        )

        logger.info(
            f"Cost optimization: {len(texts)} -> {len(unique_texts)} texts "
            f"(saved ${opt_stats['savings']['cost_saved']:.6f})"
        )

        # 3. 向量化
        embeddings_unique = await self.embedder.embed_batch(unique_texts)

        # 4. 重建原始顺序
        embeddings = [embeddings_unique[idx] for idx in indices]

        # 5. 记录实际成本
        budget_status = self.budget_manager.record_cost(opt_stats["cost"]["total_cost"])

        if budget_status["alerts"]:
            for alert in budget_status["alerts"]:
                logger.warning(f"Budget alert: {alert}")

        # 返回结果
        result = {
            "document_id": doc_id,
            "chunks_count": len(chunks),
            "embeddings": embeddings,
            "optimization_stats": opt_stats,
            "budget_status": budget_status,
        }

        return result

    async def process_documents_batch(
        self, documents: List[Dict[str, Any]], tenant_id: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        批量处理文档

        Args:
            documents: 文档列表
            tenant_id: 租户 ID

        Returns:
            处理结果列表
        """
        logger.info(f"Processing batch of {len(documents)} documents")

        results = []
        for doc in documents:
            try:
                result = await self.process_document(doc, tenant_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process document {doc.get('id')}: {e}")
                results.append(
                    {
                        "document_id": doc.get("id"),
                        "error": str(e),
                    }
                )

        return results

    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        return self.cost_optimizer.get_optimization_report()

    def get_budget_status(self) -> Dict[str, Any]:
        """获取预算状态"""
        return {
            "daily_spent": self.budget_manager.daily_spent,
            "daily_budget": self.budget_manager.daily_budget,
            "daily_remaining": self.budget_manager.daily_budget - self.budget_manager.daily_spent,
            "daily_usage_rate": self.budget_manager.daily_spent / self.budget_manager.daily_budget,
            "monthly_spent": self.budget_manager.monthly_spent,
            "monthly_budget": self.budget_manager.monthly_budget,
            "monthly_remaining": self.budget_manager.monthly_budget
            - self.budget_manager.monthly_spent,
            "monthly_usage_rate": self.budget_manager.monthly_spent
            / self.budget_manager.monthly_budget,
        }


async def demo_basic_usage():
    """基础使用演示"""
    logger.info("=== Demo 1: Basic Usage ===\n")

    # 初始化处理器
    processor = DocumentProcessorWithCostOptimization(
        enable_deduplication=True,
        daily_budget=100.0,
    )

    # 模拟文档
    document = {
        "id": "doc_001",
        "chunks": [
            {"content": "如何使用产品？"},
            {"content": "价格是多少？"},
            {"content": "如何使用产品？"},  # 重复
            {"content": "有什么优惠活动？"},
        ],
    }

    # 处理文档
    result = await processor.process_document(document, tenant_id="demo_tenant")

    logger.info(f"\n处理结果:")
    logger.info(f"  文档 ID: {result['document_id']}")
    logger.info(f"  分块数: {result['chunks_count']}")
    logger.info(f"  向量数: {len(result['embeddings'])}")

    opt_stats = result["optimization_stats"]
    logger.info(f"\n  优化统计:")
    logger.info(
        f"    去重: {opt_stats['deduplication']['original_count']} -> "
        f"{opt_stats['deduplication']['unique_count']}"
    )
    logger.info(f"    Token: {opt_stats['cost']['total_tokens']}")
    logger.info(f"    成本: ${opt_stats['cost']['total_cost']:.6f}")
    logger.info(f"    节省: ${opt_stats['savings']['cost_saved']:.6f}")

    budget_status = result["budget_status"]
    logger.info(f"\n  预算状态:")
    logger.info(
        f"    每日: ${budget_status['daily_spent']:.2f}/${budget_status['daily_budget']:.2f} "
        f"({budget_status['daily_usage_rate']:.1%})"
    )

    logger.info("")


async def demo_batch_processing():
    """批量处理演示"""
    logger.info("=== Demo 2: Batch Processing ===\n")

    processor = DocumentProcessorWithCostOptimization(
        enable_deduplication=True,
        daily_budget=100.0,
    )

    # 模拟多个文档（包含跨文档重复）
    documents = [
        {
            "id": "doc_001",
            "chunks": [
                {"content": "常见问题1"},
                {"content": "常见问题2"},
            ],
        },
        {
            "id": "doc_002",
            "chunks": [
                {"content": "常见问题1"},  # 与 doc_001 重复
                {"content": "常见问题3"},
            ],
        },
        {
            "id": "doc_003",
            "chunks": [
                {"content": "常见问题2"},  # 与 doc_001 重复
                {"content": "常见问题4"},
            ],
        },
    ]

    # 批量处理
    results = await processor.process_documents_batch(documents, tenant_id="batch_tenant")

    logger.info(f"\n批量处理完成: {len(results)} 个文档")

    total_chunks = sum(r.get("chunks_count", 0) for r in results)
    total_savings = sum(
        r.get("optimization_stats", {}).get("savings", {}).get("cost_saved", 0) for r in results
    )

    logger.info(f"  总分块数: {total_chunks}")
    logger.info(f"  总节省: ${total_savings:.6f}")

    logger.info("")


async def demo_budget_management():
    """预算管理演示"""
    logger.info("=== Demo 3: Budget Management ===\n")

    # 设置较小的预算用于演示
    processor = DocumentProcessorWithCostOptimization(
        enable_deduplication=False,  # 禁用去重以快速触发预算
        daily_budget=0.00001,  # 极小的预算
    )

    # 尝试处理大量文档
    large_document = {
        "id": "large_doc",
        "chunks": [{"content": f"文本 {i}"} for i in range(1000)],
    }

    try:
        await processor.process_document(large_document, tenant_id="budget_test")
    except RuntimeError as e:
        logger.warning(f"预期的预算超限错误: {e}")

    # 查看预算状态
    budget_status = processor.get_budget_status()
    logger.info(f"\n预算状态:")
    logger.info(f"  每日: ${budget_status['daily_spent']:.8f}/${budget_status['daily_budget']:.8f}")
    logger.info(f"  使用率: {budget_status['daily_usage_rate']:.1%}")

    logger.info("")


async def demo_optimization_report():
    """优化报告演示"""
    logger.info("=== Demo 4: Optimization Report ===\n")

    processor = DocumentProcessorWithCostOptimization(enable_deduplication=True)

    # 处理多个文档
    documents = [
        {
            "id": f"doc_{i}",
            "chunks": [
                {"content": "重复问题"},
                {"content": f"唯一问题 {i}"},
            ],
        }
        for i in range(10)
    ]

    await processor.process_documents_batch(documents, tenant_id="report_tenant")

    # 生成报告
    report = processor.get_optimization_report()

    logger.info("📊 优化报告:\n")

    # 总体统计
    total = report["total"]
    logger.info("总体统计:")
    logger.info(f"  总 Token: {total['total_tokens']:,}")
    logger.info(f"  总成本: ${total['total_cost']:.6f}")
    logger.info(f"  请求数: {total['request_count']}")

    # 按模型
    logger.info("\n按模型:")
    for model, stats in report["by_model"].items():
        logger.info(f"  {model}:")
        logger.info(f"    Token: {stats['tokens']:,}")
        logger.info(f"    成本: ${stats['cost']:.6f}")

    # 优化建议
    logger.info("\n💡 优化建议:")
    for rec in report["recommendations"]:
        logger.info(f"  {rec}")

    logger.info("")


async def demo_comparison():
    """对比演示（有/无优化）"""
    logger.info("=== Demo 5: Comparison (With/Without Optimization) ===\n")

    # 测试数据（高重复率）
    document = {
        "id": "comparison_doc",
        "chunks": [{"content": f"常见问题 {i % 5}"} for i in range(100)],  # 100个分块，5个unique
    }

    # 1. 无优化
    logger.info("无优化:")
    processor_no_opt = DocumentProcessorWithCostOptimization(enable_deduplication=False)

    result_no_opt = await processor_no_opt.process_document(document, tenant_id="no_opt")
    stats_no_opt = result_no_opt["optimization_stats"]

    logger.info(f"  处理文本数: {stats_no_opt['cost']['text_count']}")
    logger.info(f"  Token 数: {stats_no_opt['cost']['total_tokens']}")
    logger.info(f"  成本: ${stats_no_opt['cost']['total_cost']:.6f}")

    # 2. 有优化
    logger.info("\n有优化（去重）:")
    processor_opt = DocumentProcessorWithCostOptimization(enable_deduplication=True)

    result_opt = await processor_opt.process_document(document, tenant_id="opt")
    stats_opt = result_opt["optimization_stats"]

    logger.info(f"  处理文本数: {stats_opt['cost']['text_count']}")
    logger.info(f"  Token 数: {stats_opt['cost']['total_tokens']}")
    logger.info(f"  成本: ${stats_opt['cost']['total_cost']:.6f}")

    # 3. 对比
    tokens_saved = stats_no_opt["cost"]["total_tokens"] - stats_opt["cost"]["total_tokens"]
    cost_saved = stats_no_opt["cost"]["total_cost"] - stats_opt["cost"]["total_cost"]
    savings_rate = (
        cost_saved / stats_no_opt["cost"]["total_cost"]
        if stats_no_opt["cost"]["total_cost"] > 0
        else 0
    )

    logger.info("\n📊 对比结果:")
    logger.info(f"  Token 节省: {tokens_saved} ({savings_rate:.1%})")
    logger.info(f"  成本节省: ${cost_saved:.6f} ({savings_rate:.1%})")
    logger.info(f"  🎉 优化后节省了 {savings_rate:.1%} 的成本！")

    logger.info("")


async def main():
    """运行所有演示"""
    try:
        await demo_basic_usage()
        await demo_batch_processing()
        await demo_budget_management()
        await demo_optimization_report()
        await demo_comparison()

        logger.info("✅ All integration demos completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
