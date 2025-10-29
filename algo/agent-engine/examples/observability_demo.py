#!/usr/bin/env python3
"""
Agent Engine 可观测性 Demo

演示如何使用:
1. ExecutionTracer - 执行追踪
2. AgentEvaluator - 自动化评测
3. BudgetController - 预算控制
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.agent_engine import AgentEngine
from app.core.budget_controller import BudgetController, BudgetTier
from app.observability.tracer import ExecutionTracer, set_tracer
from tests.eval.agent.evaluator import AgentEvaluator, TestCase

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_execution_tracing():
    """演示执行追踪"""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 1: Execution Tracing")
    logger.info("=" * 60)

    # 创建追踪器
    tracer = ExecutionTracer(enable_otel=False)  # 本地 Demo，禁用 OTEL
    set_tracer(tracer)

    # 初始化 Agent Engine
    agent_engine = AgentEngine()
    await agent_engine.initialize()

    # 执行任务
    task_id = "demo_task_001"
    task = "Calculate (25 * 4 + 10) / 2"

    logger.info(f"Starting task: {task}")
    tracer.start_task(task_id, task, mode="react")

    # 模拟执行过程
    tracer.record_thought(task_id, "I need to calculate (25 * 4 + 10) / 2")
    tracer.record_action(
        task_id, "Use calculator", "calculator", {"expression": "(25 * 4 + 10) / 2"}
    )
    tracer.record_tool_call(
        task_id, "calculator", {"expression": "(25 * 4 + 10) / 2"}, 50, True, "60"
    )
    tracer.record_observation(task_id, "60")
    tracer.record_llm_call(task_id, "gpt-4", 50, 20, 500, 0.002)

    tracer.end_task(task_id, "The answer is 60", success=True)

    # 获取追踪摘要
    summary = tracer.get_trace_summary(task_id)
    logger.info("\nTrace Summary:")
    logger.info(f"  Steps: {summary['step_count']}")
    logger.info(f"  Tool Calls: {summary['tool_calls_count']}")
    logger.info(f"  LLM Calls: {summary['llm_calls_count']}")
    logger.info(f"  Duration: {summary['total_duration_ms']:.0f} ms")
    logger.info(f"  Tokens: {summary['total_tokens']}")
    logger.info(f"  Cost: ${summary['total_cost_usd']:.4f}")

    # 导出 JSON
    trace_json = tracer.export_trace_json(task_id)
    logger.info(f"\nTrace exported (length: {len(trace_json)} chars)")

    await agent_engine.cleanup()


async def demo_evaluation():
    """演示自动化评测"""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 2: Automated Evaluation")
    logger.info("=" * 60)

    # 创建测试用例
    test_cases = [
        TestCase(
            id="calc_demo_001",
            category="simple_calculation",
            task="Calculate 10 + 20 * 3",
            expected_answer="70",
            expected_tools=["calculator"],
            max_steps=3,
        ),
        TestCase(
            id="calc_demo_002",
            category="simple_calculation",
            task="Calculate 100 / 5",
            expected_answer="20",
            expected_tools=["calculator"],
            max_steps=3,
        ),
    ]

    # 初始化评测器
    agent_engine = AgentEngine()
    await agent_engine.initialize()

    evaluator = AgentEvaluator(
        agent_engine=agent_engine,
        enable_llm_judge=False,  # Demo 中禁用
    )

    # 运行评测
    logger.info(f"Running evaluation with {len(test_cases)} test cases...")
    results = await evaluator.evaluate(test_cases=test_cases, modes=["react"], save_traces=False)

    # 生成报告
    report = evaluator.generate_report(results)

    # 打印摘要
    evaluator.print_summary(report)

    await agent_engine.cleanup()


async def demo_budget_control():
    """演示预算控制"""
    logger.info("\n" + "=" * 60)
    logger.info("Demo 3: Budget Control")
    logger.info("=" * 60)

    # 创建预算控制器（无 Redis，使用内存）
    controller = BudgetController(
        redis_client=None,
        default_tier=BudgetTier.FREE,  # $0.10/day
        alert_threshold=0.8,
        enable_auto_fallback=True,
    )

    tenant_id = "demo_tenant_123"

    # 模拟多次请求
    logger.info(f"\nSimulating API calls for tenant: {tenant_id}")
    logger.info(f"Budget: ${controller.tier_budgets[BudgetTier.FREE]:.2f}/day")

    for i in range(15):
        cost = 0.01  # $0.01 per request

        # 检查预算
        can_proceed = await controller.check_budget(tenant_id, cost)

        if can_proceed:
            # 模拟任务执行
            logger.info(f"Request {i + 1}: ✅ Approved (cost: ${cost:.2f})")
            await controller.record_cost(tenant_id, cost, {"request_id": f"req_{i + 1}"})
        else:
            # 预算耗尽，获取降级策略
            strategy = await controller.get_fallback_strategy(tenant_id)
            logger.warning(f"Request {i + 1}: ❌ Budget exceeded, fallback: {strategy.value}")
            break

    # 获取使用报告
    report = await controller.get_usage_report(tenant_id, days=1)
    logger.info("\nUsage Report:")
    logger.info(f"  Total Usage: ${report['total_usage']:.4f}")
    logger.info(f"  Budget: ${report['daily_budget']:.2f}")
    logger.info(f"  Usage Ratio: {report['usage_ratio']:.2%}")

    # 获取优化建议
    suggestions = await controller.get_optimization_suggestions(tenant_id)
    if suggestions:
        logger.info("\nOptimization Suggestions:")
        for suggestion in suggestions:
            logger.info(f"  💡 {suggestion}")


async def main():
    """主函数"""
    logger.info("\n" + "=" * 70)
    logger.info("Agent Engine Observability Demo")
    logger.info("=" * 70)

    try:
        # Demo 1: 执行追踪
        await demo_execution_tracing()

        # Demo 2: 自动化评测
        # await demo_evaluation()  # 需要完整的 Agent Engine，暂时注释

        # Demo 3: 预算控制
        await demo_budget_control()

        logger.info("\n" + "=" * 70)
        logger.info("✅ All demos completed successfully!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
