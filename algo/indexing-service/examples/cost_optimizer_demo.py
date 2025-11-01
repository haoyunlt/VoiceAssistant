"""
成本优化器演示

展示文本去重、Token 计费、成本计算和优化建议
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_token_counter():
    """Token 计数器演示"""
    logger.info("=== Demo 1: Token Counter ===\n")

    from app.core.cost_optimizer import TokenCounter

    # 初始化
    token_counter = TokenCounter(model_name="gpt-3.5-turbo")

    # 测试文本
    texts = [
        "Hello, world!",
        "这是一段中文文本",
        "Mixed text: 中英文混合，包含数字 123",
        "A" * 1000,  # 长文本
    ]

    logger.info("Counting tokens for various texts:")
    for text in texts:
        token_count = token_counter.count_tokens(text)
        preview = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"  '{preview}': {token_count} tokens")

    # 批量计数
    logger.info("\nBatch counting:")
    token_counts = token_counter.count_tokens_batch(texts)
    total_tokens = sum(token_counts)
    logger.info(f"  Total: {total_tokens} tokens")

    # 成本估算
    logger.info("\nCost estimation:")
    models = ["text-embedding-ada-002", "text-embedding-3-small", "bge-m3"]

    for model in models:
        cost = token_counter.estimate_cost(total_tokens, model)
        logger.info(f"  {model}: ${cost:.6f}")

    logger.info()


async def demo_text_deduplicator():
    """文本去重器演示"""
    logger.info("=== Demo 2: Text Deduplicator ===\n")

    from app.core.cost_optimizer import TextDeduplicator

    # 初始化
    deduplicator = TextDeduplicator(use_hash=True)

    # 测试数据（包含重复）
    texts = [
        "如何使用产品？",
        "价格是多少？",
        "如何使用产品？",  # 重复
        "有什么优惠活动？",
        "价格是多少？",  # 重复
        "支持哪些支付方式？",
        "如何使用产品？",  # 重复
    ]

    logger.info(f"Original texts ({len(texts)}):")
    for i, text in enumerate(texts):
        logger.info(f"  [{i}] {text}")

    # 去重
    unique_texts, indices, stats = deduplicator.deduplicate(texts)

    logger.info(f"\nUnique texts ({len(unique_texts)}):")
    for i, text in enumerate(unique_texts):
        logger.info(f"  [{i}] {text}")

    logger.info(f"\nReconstruction indices: {indices}")

    logger.info(f"\nDeduplication stats:")
    logger.info(f"  Original: {stats['original_count']}")
    logger.info(f"  Unique: {stats['unique_count']}")
    logger.info(f"  Duplicates: {stats['duplicates']}")
    logger.info(f"  Deduplication rate: {stats['deduplication_rate']:.1%}")

    # 验证重建
    logger.info("\nReconstruction verification:")
    reconstructed = [unique_texts[idx] for idx in indices]
    logger.info(f"  Match: {reconstructed == texts}")

    logger.info()


async def demo_cost_calculator():
    """成本计算器演示"""
    logger.info("=== Demo 3: Cost Calculator ===\n")

    from app.core.cost_optimizer import CostCalculator, TokenCounter

    # 初始化
    token_counter = TokenCounter()
    cost_calculator = CostCalculator(token_counter)

    # 模拟多个请求
    requests = [
        {
            "texts": ["文本1", "文本2", "文本3"],
            "model": "text-embedding-ada-002",
            "tenant_id": "tenant_A",
        },
        {
            "texts": ["长文本" * 100],
            "model": "text-embedding-3-small",
            "tenant_id": "tenant_B",
        },
        {
            "texts": ["短文本"] * 10,
            "model": "bge-m3",
            "tenant_id": "tenant_A",
        },
    ]

    logger.info("Processing requests:")
    for i, req in enumerate(requests, 1):
        result = cost_calculator.calculate_cost(
            texts=req["texts"],
            model=req["model"],
            tenant_id=req["tenant_id"],
        )

        logger.info(f"\n  Request {i}:")
        logger.info(f"    Texts: {result['text_count']}")
        logger.info(f"    Total tokens: {result['total_tokens']}")
        logger.info(f"    Avg tokens/text: {result['avg_tokens_per_text']:.1f}")
        logger.info(f"    Total cost: ${result['total_cost']:.6f}")
        logger.info(f"    Model: {result['model']}")
        logger.info(f"    Tenant: {result['tenant_id']}")

    # 总体统计
    logger.info("\n📊 Total Statistics:")
    total_stats = cost_calculator.get_total_stats()
    logger.info(f"  Total tokens: {total_stats['total_tokens']:,}")
    logger.info(f"  Total cost: ${total_stats['total_cost']:.6f}")
    logger.info(f"  Requests: {total_stats['request_count']}")
    logger.info(f"  Avg tokens/request: {total_stats['avg_tokens_per_request']:.1f}")

    # 按模型统计
    logger.info("\n📊 By Model:")
    for model, stats in cost_calculator.get_stats_by_model().items():
        logger.info(f"  {model}:")
        logger.info(f"    Tokens: {stats['tokens']:,}")
        logger.info(f"    Cost: ${stats['cost']:.6f}")
        logger.info(f"    Requests: {stats['requests']}")

    # 按租户统计
    logger.info("\n📊 By Tenant:")
    for tenant_id, stats in cost_calculator.get_stats_by_tenant().items():
        logger.info(f"  {tenant_id}:")
        logger.info(f"    Tokens: {stats['tokens']:,}")
        logger.info(f"    Cost: ${stats['cost']:.6f}")
        logger.info(f"    Requests: {stats['requests']}")

    logger.info()


async def demo_cost_optimizer():
    """成本优化器演示"""
    logger.info("=== Demo 4: Cost Optimizer (Integrated) ===\n")

    from app.core.cost_optimizer import CostOptimizer

    # 初始化
    optimizer = CostOptimizer(
        model_name="text-embedding-ada-002",
        enable_deduplication=True,
    )

    # 测试数据（包含大量重复）
    texts = [
        "常见问题1",
        "常见问题2",
        "常见问题3",
    ] * 50  # 150个文本，实际只有3个unique

    logger.info(f"Processing {len(texts)} texts ({len(set(texts))} unique)...")

    # 优化并计算
    unique_texts, indices, stats = optimizer.optimize_and_calculate(
        texts=texts,
        model="text-embedding-ada-002",
        tenant_id="demo_tenant",
    )

    logger.info(f"\n📊 Optimization Results:")
    logger.info(f"\n  Deduplication:")
    logger.info(f"    Original: {stats['deduplication']['original_count']}")
    logger.info(f"    Unique: {stats['deduplication']['unique_count']}")
    logger.info(
        f"    Duplicates: {stats['deduplication']['duplicates']} "
        f"({stats['deduplication']['deduplication_rate']:.1%})"
    )

    logger.info(f"\n  Cost (after deduplication):")
    logger.info(f"    Texts: {stats['cost']['text_count']}")
    logger.info(f"    Tokens: {stats['cost']['total_tokens']:,}")
    logger.info(f"    Cost: ${stats['cost']['total_cost']:.6f}")

    logger.info(f"\n  Savings:")
    logger.info(f"    Tokens saved: {stats['savings']['tokens_saved']:,}")
    logger.info(f"    Cost saved: ${stats['savings']['cost_saved']:.6f}")
    logger.info(f"    Savings rate: {stats['savings']['savings_rate']:.1%}")

    logger.info()


async def demo_optimization_report():
    """优化报告演示"""
    logger.info("=== Demo 5: Optimization Report ===\n")

    from app.core.cost_optimizer import CostOptimizer

    # 初始化
    optimizer = CostOptimizer(
        model_name="text-embedding-3-large",
        enable_deduplication=True,
    )

    # 模拟多个请求
    scenarios = [
        (["短文本"] * 100, "text-embedding-3-large", "tenant_A"),
        (["长文本" * 50] * 50, "text-embedding-ada-002", "tenant_B"),
        (["问题" + str(i) for i in range(1000)], "bge-m3", "tenant_A"),
    ]

    logger.info("Simulating multiple requests...")
    for texts, model, tenant_id in scenarios:
        optimizer.optimize_and_calculate(texts, model, tenant_id)

    # 生成报告
    logger.info("\n📋 Optimization Report:\n")
    report = optimizer.get_optimization_report()

    # 总体统计
    logger.info("📊 Total Statistics:")
    total = report["total"]
    logger.info(f"  Total tokens: {total['total_tokens']:,}")
    logger.info(f"  Total cost: ${total['total_cost']:.2f}")
    logger.info(f"  Requests: {total['request_count']}")
    logger.info(f"  Avg tokens/request: {total['avg_tokens_per_request']:.1f}")

    # 按模型
    logger.info("\n📊 By Model:")
    for model, stats in report["by_model"].items():
        logger.info(f"  {model}:")
        logger.info(f"    Cost: ${stats['cost']:.6f}")
        logger.info(f"    Tokens: {stats['tokens']:,}")

    # 按租户
    logger.info("\n📊 By Tenant:")
    for tenant_id, stats in report["by_tenant"].items():
        logger.info(f"  {tenant_id}:")
        logger.info(f"    Cost: ${stats['cost']:.6f}")
        logger.info(f"    Tokens: {stats['tokens']:,}")

    # 优化建议
    logger.info("\n💡 Recommendations:")
    for rec in report["recommendations"]:
        logger.info(f"  {rec}")

    logger.info()


async def demo_budget_manager():
    """预算管理器演示"""
    logger.info("=== Demo 6: Budget Manager ===\n")

    from app.core.cost_optimizer import CostBudgetManager

    # 初始化（设置较小的预算用于演示）
    budget_manager = CostBudgetManager(
        daily_budget=10.0,
        monthly_budget=300.0,
        alert_threshold=0.8,
    )

    logger.info("Initial budget:")
    logger.info(f"  Daily: $10.00")
    logger.info(f"  Monthly: $300.00")
    logger.info(f"  Alert threshold: 80%")

    # 模拟成本记录
    costs = [1.5, 2.0, 3.5, 4.0]  # 累计 $11，超过每日预算

    logger.info("\nRecording costs:")
    for i, cost in enumerate(costs, 1):
        status = budget_manager.record_cost(cost)

        logger.info(f"\n  Cost #{i}: ${cost:.2f}")
        logger.info(
            f"    Daily: ${status['daily_spent']:.2f}/${status['daily_budget']:.2f} "
            f"({status['daily_usage_rate']:.1%})"
        )
        logger.info(
            f"    Monthly: ${status['monthly_spent']:.2f}/${status['monthly_budget']:.2f} "
            f"({status['monthly_usage_rate']:.1%})"
        )

        if status["alerts"]:
            logger.info(f"    Alerts:")
            for alert in status["alerts"]:
                logger.info(f"      {alert}")

    # 检查预算
    logger.info("\nChecking budget for new request ($5.00):")
    can_proceed, message = budget_manager.check_budget(5.0)
    logger.info(f"  Can proceed: {can_proceed}")
    logger.info(f"  Message: {message}")

    logger.info()


async def demo_comparison():
    """成本对比演示"""
    logger.info("=== Demo 7: Cost Comparison (With/Without Optimization) ===\n")

    from app.core.cost_optimizer import CostOptimizer

    # 测试数据（高重复率）
    texts = ["常见问题" + str(i % 10) for i in range(1000)]  # 1000个文本，10个unique

    logger.info(f"Test data: {len(texts)} texts, {len(set(texts))} unique\n")

    # 无优化
    logger.info("Without optimization:")
    optimizer_disabled = CostOptimizer(
        model_name="text-embedding-ada-002",
        enable_deduplication=False,
    )

    _, _, stats_no_opt = optimizer_disabled.optimize_and_calculate(
        texts, "text-embedding-ada-002"
    )

    logger.info(f"  Texts processed: {stats_no_opt['cost']['text_count']}")
    logger.info(f"  Tokens: {stats_no_opt['cost']['total_tokens']:,}")
    logger.info(f"  Cost: ${stats_no_opt['cost']['total_cost']:.6f}")

    # 有优化
    logger.info("\nWith optimization (deduplication):")
    optimizer_enabled = CostOptimizer(
        model_name="text-embedding-ada-002",
        enable_deduplication=True,
    )

    _, _, stats_opt = optimizer_enabled.optimize_and_calculate(
        texts, "text-embedding-ada-002"
    )

    logger.info(f"  Texts processed: {stats_opt['cost']['text_count']}")
    logger.info(f"  Tokens: {stats_opt['cost']['total_tokens']:,}")
    logger.info(f"  Cost: ${stats_opt['cost']['total_cost']:.6f}")

    # 对比
    logger.info("\n📊 Comparison:")
    tokens_saved = (
        stats_no_opt["cost"]["total_tokens"] - stats_opt["cost"]["total_tokens"]
    )
    cost_saved = stats_no_opt["cost"]["total_cost"] - stats_opt["cost"]["total_cost"]
    savings_rate = cost_saved / stats_no_opt["cost"]["total_cost"]

    logger.info(f"  Tokens saved: {tokens_saved:,} ({savings_rate:.1%})")
    logger.info(f"  Cost saved: ${cost_saved:.6f} ({savings_rate:.1%})")
    logger.info(f"  🎉 Optimization reduced cost by {savings_rate:.1%}!")

    logger.info()


async def main():
    """运行所有演示"""
    try:
        await demo_token_counter()
        await demo_text_deduplicator()
        await demo_cost_calculator()
        await demo_cost_optimizer()
        await demo_optimization_report()
        await demo_budget_manager()
        await demo_comparison()

        logger.info("✅ All demos completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())

