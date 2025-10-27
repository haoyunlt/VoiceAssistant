#!/usr/bin/env python3
"""
手动测试工具功能

运行此脚本可以交互式测试所有工具
"""

import asyncio
import os

from app.tools.dynamic_registry import get_tool_registry


async def test_all_tools():
    """测试所有工具"""
    print("=" * 80)
    print("Agent Engine - 工具系统手动测试")
    print("=" * 80)
    print()

    # 获取工具注册表
    registry = get_tool_registry()

    print(f"📋 已加载 {len(registry.get_tool_names())} 个工具:")
    for name in registry.get_tool_names():
        print(f"  - {name}")
    print()

    # 测试 1: 计算器
    print("🧮 测试 1: 计算器工具")
    print("-" * 40)
    result = await registry.execute_tool("calculator", {"expression": "2 ** 10 + 5 * 3"})
    print(f"表达式: 2 ** 10 + 5 * 3")
    print(f"结果: {result}")
    print()

    # 测试 2: 当前时间
    print("⏰ 测试 2: 当前时间工具")
    print("-" * 40)
    result = await registry.execute_tool("current_time", {})
    print(result)
    print()

    # 测试 3: 搜索（可能是模拟结果）
    print("🔍 测试 3: 搜索工具")
    print("-" * 40)
    if os.getenv("SERPAPI_KEY"):
        print("✅ SERPAPI_KEY 已配置，将返回真实搜索结果")
    else:
        print("⚠️  SERPAPI_KEY 未配置，将返回模拟结果")

    result = await registry.execute_tool("search", {"query": "Python编程", "num_results": 3})
    print(f"搜索: Python编程")
    print(f"结果:\n{result[:500]}...")
    print()

    # 测试 4: 天气（可能是模拟结果）
    print("🌤️  测试 4: 天气工具")
    print("-" * 40)
    if os.getenv("OPENWEATHER_API_KEY"):
        print("✅ OPENWEATHER_API_KEY 已配置，将返回真实天气数据")
    else:
        print("⚠️  OPENWEATHER_API_KEY 未配置，将返回模拟结果")

    result = await registry.execute_tool("weather", {"city": "北京"})
    print(f"城市: 北京")
    print(f"结果:\n{result}")
    print()

    # 测试 5: 知识库（可能是模拟结果）
    print("📚 测试 5: 知识库工具")
    print("-" * 40)
    rag_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8006")
    print(f"RAG Engine URL: {rag_url}")

    result = await registry.execute_tool(
        "knowledge_base", {"query": "测试查询", "knowledge_base_id": "default", "top_k": 3}
    )
    print(f"查询: 测试查询")
    print(f"结果:\n{result[:500]}...")
    print()

    # 显示工具定义
    print("📖 工具定义（OpenAI Function Calling 格式）")
    print("-" * 40)
    definitions = registry.get_tool_definitions_for_llm()
    print(f"共 {len(definitions)} 个工具定义:")
    for definition in definitions:
        func = definition["function"]
        print(f"\n  - {func['name']}: {func['description'][:60]}...")

    print()
    print("=" * 80)
    print("✅ 测试完成!")
    print("=" * 80)
    print()

    # 配置提示
    print("💡 提示:")
    if not os.getenv("SERPAPI_KEY"):
        print("  - 配置 SERPAPI_KEY 以启用真实搜索功能")
    if not os.getenv("OPENWEATHER_API_KEY"):
        print("  - 配置 OPENWEATHER_API_KEY 以启用真实天气查询")
    print("  - 确保 RAG Engine 正在运行以启用知识库功能")
    print()


if __name__ == "__main__":
    asyncio.run(test_all_tools())
