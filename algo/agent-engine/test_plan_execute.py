"""
Plan-Execute 执行器测试脚本

测试 Plan-Execute 模式的任务分解和执行
"""

import asyncio
import sys

# 添加项目路径
sys.path.insert(0, ".")

from app.executors.plan_execute_executor import get_plan_execute_executor
from app.tools.dynamic_registry import get_tool_registry


async def test_basic_plan():
    """测试基础规划"""
    print("\n=== 测试 1: 基础规划 ===\n")

    executor = get_plan_execute_executor()

    # 简单任务
    task = "搜索 Python 编程资讯"

    print(f"任务: {task}\n")

    # 生成计划
    available_tools = executor._get_available_tools()
    plan = await executor.planner.create_plan(task, available_tools)

    print(f"规划推理: {plan.reasoning}\n")
    print(f"执行步骤 ({len(plan.steps)} 步):")
    for step in plan.steps:
        print(f"  步骤 {step.step_id}: {step.description}")
        if step.tool:
            print(f"    工具: {step.tool}, 参数: {step.tool_args}")
        if step.depends_on:
            print(f"    依赖: {step.depends_on}")
    print()


async def test_complex_task():
    """测试复杂任务执行"""
    print("\n=== 测试 2: 复杂任务执行 ===\n")

    executor = get_plan_execute_executor()

    # 复杂任务（需要多步骤）
    task = "搜索北京的天气，如果下雨提醒带伞"

    print(f"任务: {task}\n")

    # 执行任务
    trace = await executor.execute(task)

    print(f"执行状态: {'成功' if trace.success else '失败'}")
    print(f"总耗时: {trace.total_time_ms:.2f}ms\n")

    print("执行追踪:")
    for result in trace.step_results:
        status = "✓" if result.success else "✗"
        print(
            f"  {status} 步骤 {result.step_id}: {result.result[:100]}... ({result.execution_time_ms:.2f}ms)"
        )
        if result.error:
            print(f"    错误: {result.error}")

    print(f"\n最终答案:\n{trace.final_answer}\n")


async def test_calculator():
    """测试计算器任务"""
    print("\n=== 测试 3: 计算器任务 ===\n")

    executor = get_plan_execute_executor()

    task = "计算 (100 + 50) * 2 的结果"

    print(f"任务: {task}\n")

    trace = await executor.execute(task)

    print(f"执行状态: {'成功' if trace.success else '失败'}")
    print(f"总耗时: {trace.total_time_ms:.2f}ms\n")

    print("执行计划:")
    for step in trace.plan.steps:
        print(f"  步骤 {step.step_id}: {step.description}")

    print(f"\n最终答案:\n{trace.final_answer}\n")


async def test_weather():
    """测试天气查询任务"""
    print("\n=== 测试 4: 天气查询任务 ===\n")

    executor = get_plan_execute_executor()

    task = "查询北京今天的天气"

    print(f"任务: {task}\n")

    trace = await executor.execute(task)

    print(f"执行状态: {'成功' if trace.success else '失败'}")
    print(f"总耗时: {trace.total_time_ms:.2f}ms\n")

    print(f"最终答案:\n{trace.final_answer}\n")


async def test_knowledge_base():
    """测试知识库查询任务"""
    print("\n=== 测试 5: 知识库查询任务 ===\n")

    executor = get_plan_execute_executor()

    task = "查询公司的休假政策"

    print(f"任务: {task}\n")

    trace = await executor.execute(task)

    print(f"执行状态: {'成功' if trace.success else '失败'}")
    print(f"总耗时: {trace.total_time_ms:.2f}ms\n")

    print(f"最终答案:\n{trace.final_answer}\n")


async def test_all():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print(" Plan-Execute 执行器测试")
    print("=" * 60)

    # 初始化工具注册表
    registry = get_tool_registry()
    print(f"\n可用工具: {registry.get_tool_names()}")

    # 运行测试
    await test_basic_plan()
    await test_calculator()
    await test_weather()
    await test_knowledge_base()
    # await test_complex_task()  # 这个可能需要实际的搜索 API

    print("\n" + "=" * 60)
    print(" 所有测试完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_all())
