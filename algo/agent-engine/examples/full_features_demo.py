"""
完整功能演示

展示 Agent Engine v2.0 的所有主要功能。
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.budget_controller import BudgetController, BudgetTier
from app.core.context_manager import ContextManager, Priority
from app.observability.tracer import ExecutionTracer, set_tracer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_1_observability():
    """Demo 1: 执行追踪和可观测性"""
    print("\n" + "=" * 70)
    print("Demo 1: 执行追踪和可观测性")
    print("=" * 70)

    # 创建追踪器
    tracer = ExecutionTracer(enable_otel=False)
    set_tracer(tracer)

    # 模拟任务执行
    task_id = "demo_task_001"
    tracer.start_task(task_id, "Calculate (10 + 20) * 3", mode="react")

    # 模拟思考过程
    tracer.record_thought(task_id, "I need to calculate (10 + 20) * 3")
    tracer.record_action(task_id, "Use calculator", "calculator", {"expression": "(10 + 20) * 3"})

    # 模拟工具调用
    tracer.record_tool_call(
        task_id, "calculator", {"expression": "(10 + 20) * 3"}, 45, True, "90"
    )

    # 模拟 LLM 调用
    tracer.record_llm_call(task_id, "gpt-4", 100, 50, 800, 0.005)

    tracer.record_observation(task_id, "The result is 90")
    tracer.end_task(task_id, "The answer is 90", success=True)

    # 获取追踪摘要
    summary = tracer.get_trace_summary(task_id)
    print("\n📊 追踪摘要:")
    print(f"  ✅ 任务: {summary['task_id']}")
    print(f"  ✅ 步骤数: {summary['step_count']}")
    print(f"  ✅ 工具调用: {summary['tool_calls_count']}")
    print(f"  ✅ LLM 调用: {summary['llm_calls_count']}")
    print(f"  ✅ 总耗时: {summary['total_duration_ms']:.0f}ms")
    print(f"  ✅ Token 消耗: {summary['total_tokens']}")
    print(f"  ✅ 成本: ${summary['total_cost_usd']:.4f}")

    print("\n✅ Demo 1 完成！")


async def demo_2_budget_control():
    """Demo 2: 成本控制与预算管理"""
    print("\n" + "=" * 70)
    print("Demo 2: 成本控制与预算管理")
    print("=" * 70)

    controller = BudgetController(
        redis_client=None,  # 内存模式
        default_tier=BudgetTier.BASIC,  # $1.00/day
        alert_threshold=0.8,
    )

    tenant_id = "tenant_demo"

    print("\n💰 预算配置:")
    print(f"  等级: {BudgetTier.BASIC.value}")
    print("  预算: $1.00/day")
    print("  告警阈值: 80%")

    # 模拟多次 API 调用
    print("\n📊 模拟 API 调用:")
    for i in range(20):
        cost = 0.06  # 每次 $0.06
        can_proceed = await controller.check_budget(tenant_id, cost)

        if can_proceed:
            await controller.record_cost(tenant_id, cost)
            print(f"  [{i + 1}] ✅ 请求通过 (成本: ${cost:.2f})")
        else:
            strategy = await controller.get_fallback_strategy(tenant_id)
            print(f"  [{i + 1}] ⚠️  预算不足，降级策略: {strategy.value}")
            break

    # 获取使用报告
    report = await controller.get_usage_report(tenant_id, days=1)
    print("\n📈 使用报告:")
    print(f"  总消耗: ${report['total_usage']:.2f}")
    print(f"  日均消耗: ${report['daily_average']:.2f}")
    print(f"  预算使用率: {report['usage_ratio']:.1%}")

    # 获取优化建议
    suggestions = await controller.get_optimization_suggestions(tenant_id)
    if suggestions:
        print("\n💡 优化建议:")
        for suggestion in suggestions:
            print(f"  - {suggestion}")

    print("\n✅ Demo 2 完成！")


async def demo_3_context_management():
    """Demo 3: 上下文窗口管理"""
    print("\n" + "=" * 70)
    print("Demo 3: 上下文窗口管理")
    print("=" * 70)

    manager = ContextManager(max_tokens=2000, model="gpt-4")

    # 添加各种组件
    print("\n📝 添加上下文组件:")

    manager.add_component(
        "system_prompt",
        "You are a helpful AI assistant specialized in Python programming.",
        Priority.CRITICAL,
    )
    print("  ✅ 系统提示 (CRITICAL)")

    manager.add_component(
        "task", "Write a Python function to calculate fibonacci numbers.", Priority.CRITICAL
    )
    print("  ✅ 任务描述 (CRITICAL)")

    manager.add_component(
        "recent_messages",
        "User: Can you help me?\nAssistant: Of course! What do you need?",
        Priority.HIGH,
    )
    print("  ✅ 最近对话 (HIGH)")

    manager.add_component(
        "memory",
        "User prefers Python 3.11+ and type hints. Likes clean code.",
        Priority.MEDIUM,
    )
    print("  ✅ 长时记忆 (MEDIUM)")

    manager.add_component(
        "tools",
        "Available tools: python_executor, code_analyzer, documentation_search",
        Priority.MEDIUM,
    )
    print("  ✅ 工具描述 (MEDIUM)")

    manager.add_component(
        "examples",
        "Example 1: def add(a, b): return a + b\nExample 2: ...",
        Priority.LOW,
    )
    print("  ✅ 示例代码 (LOW)")

    # 构建最终上下文
    context = manager.build_context()

    # 获取统计
    stats = manager.get_stats()
    print("\n📊 上下文统计:")
    print(f"  组件数: {stats['total_components']}")
    print(f"  总 Token: {stats['total_tokens']}")
    print(f"  可用 Token: {stats['available_tokens']}")
    print(f"  使用率: {stats['usage_ratio']:.1%}")

    print("\n📄 按类型分布:")
    for comp_type, tokens in stats["by_type"].items():
        print(f"  {comp_type}: {tokens} tokens")

    print(f"\n✨ 构建的上下文长度: {len(context)} 字符")

    print("\n✅ Demo 3 完成！")


async def demo_4_all_together():
    """Demo 4: 综合应用"""
    print("\n" + "=" * 70)
    print("Demo 4: 综合应用 - 完整工作流")
    print("=" * 70)

    # 初始化所有组件
    tracer = ExecutionTracer(enable_otel=False)
    set_tracer(tracer)

    budget_controller = BudgetController(default_tier=BudgetTier.PRO)
    context_manager = ContextManager(max_tokens=4000)

    print("\n🚀 执行完整工作流:")

    task_id = "comprehensive_task"
    tenant_id = "tenant_prod"

    # 1. 检查预算
    print("\n1️⃣  检查预算...")
    estimated_cost = 0.05
    if not await budget_controller.check_budget(tenant_id, estimated_cost):
        print("  ❌ 预算不足，任务中止")
        return

    print(f"  ✅ 预算充足 (预估成本: ${estimated_cost:.2f})")

    # 2. 开始追踪
    print("\n2️⃣  开始任务追踪...")
    tracer.start_task(task_id, "Analyze code quality for repository", mode="react")
    print("  ✅ 追踪已启动")

    # 3. 构建上下文
    print("\n3️⃣  构建智能上下文...")
    context_manager.add_component("task", "Analyze code quality", Priority.CRITICAL)
    context_manager.add_component("memory", "Previous analysis: 85% quality", Priority.HIGH)
    context_manager.add_component("tools", "code_analyzer, linter", Priority.MEDIUM)
    context_manager.build_context()
    print(f"  ✅ 上下文构建完成 ({context_manager.get_stats()['total_tokens']} tokens)")

    # 4. 模拟执行
    print("\n4️⃣  执行任务...")
    tracer.record_thought(task_id, "I will analyze the code using static analysis tools")
    tracer.record_action(task_id, "Run linter", "code_analyzer", {"path": "/src"})
    tracer.record_tool_call(task_id, "code_analyzer", {"path": "/src"}, 1200, True, "Analysis complete")
    print("  ✅ 任务执行中...")

    # 5. 记录成本
    print("\n5️⃣  记录实际成本...")
    actual_cost = 0.048
    await budget_controller.record_cost(tenant_id, actual_cost)
    print(f"  ✅ 成本已记录: ${actual_cost:.3f}")

    # 6. 结束追踪
    print("\n6️⃣  完成任务...")
    tracer.end_task(task_id, "Code quality: 88%, Good practices observed", success=True)

    # 7. 生成报告
    print("\n7️⃣  生成报告...")
    summary = tracer.get_trace_summary(task_id)
    cost_report = budget_controller.get_cost_breakdown()

    print("\n📊 执行报告:")
    print(f"  任务: {summary['task_id']}")
    print("  状态: ✅ 成功")
    print(f"  步骤: {summary['step_count']}")
    print(f"  耗时: {summary['total_duration_ms']:.0f}ms")
    print(f"  成本: ${cost_report['current_cost']:.4f}")
    print(f"  预算使用: {cost_report['current_cost'] / cost_report['max_budget']:.1%}")

    print("\n✅ Demo 4 完成！完整工作流执行成功！")


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🎉 Agent Engine v2.0 完整功能演示")
    print("=" * 70)
    print("\n本演示将展示以下功能：")
    print("  1. 执行追踪和可观测性")
    print("  2. 成本控制与预算管理")
    print("  3. 上下文窗口管理")
    print("  4. 综合应用（完整工作流）")

    try:
        # 运行所有 Demo
        await demo_1_observability()
        await demo_2_budget_control()
        await demo_3_context_management()
        await demo_4_all_together()

        print("\n" + "=" * 70)
        print("🎊 所有演示完成！")
        print("=" * 70)
        print("\n💡 提示:")
        print("  - 查看 docs/roadmap/ 了解更多功能")
        print("  - 运行 make eval 执行完整评测")
        print("  - 访问 http://localhost:8010/docs 查看 API 文档")
        print("\n✨ 开始使用 Agent Engine v2.0 构建你的智能应用吧！")

    except Exception as e:
        logger.error(f"Demo 执行失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
