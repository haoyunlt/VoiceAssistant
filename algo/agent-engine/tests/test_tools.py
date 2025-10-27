"""
工具系统测试

测试所有内置工具的功能
"""

import asyncio

import pytest
from app.tools.dynamic_registry import DynamicToolRegistry
from app.tools.real_tools import (
    CalculatorTool,
    CurrentTimeTool,
    KnowledgeBaseTool,
    SearchTool,
    WeatherTool,
)


@pytest.mark.asyncio
async def test_calculator_tool():
    """测试计算器工具"""
    tool = CalculatorTool()

    # 测试基本运算
    result = await tool.execute("2 + 3")
    assert "5" in result

    # 测试复杂表达式
    result = await tool.execute("(10 + 5) * 2 - 8 / 4")
    assert "28" in result

    # 测试幂运算
    result = await tool.execute("2 ** 10")
    assert "1024" in result

    # 测试取模
    result = await tool.execute("17 % 5")
    assert "2" in result

    # 测试错误表达式
    result = await tool.execute("2 / 0")
    assert "错误" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_current_time_tool():
    """测试当前时间工具"""
    tool = CurrentTimeTool()

    result = await tool.execute()
    assert "当前时间" in result
    assert "日期" in result
    assert "星期" in result


@pytest.mark.asyncio
async def test_search_tool():
    """测试搜索工具"""
    tool = SearchTool()

    # 无论是否配置 API key，都应该返回结果（真实或模拟）
    result = await tool.execute("Python 编程")
    assert result is not None
    assert len(result) > 0


@pytest.mark.asyncio
async def test_weather_tool():
    """测试天气工具"""
    tool = WeatherTool()

    # 无论是否配置 API key，都应该返回结果（真实或模拟）
    result = await tool.execute("北京")
    assert result is not None
    assert "天气" in result or "weather" in result.lower()


@pytest.mark.asyncio
async def test_knowledge_base_tool():
    """测试知识库工具"""
    tool = KnowledgeBaseTool()

    # 无论是否连接到 RAG Engine，都应该返回结果（真实或模拟）
    result = await tool.execute("测试查询")
    assert result is not None
    assert len(result) > 0


def test_tool_definitions():
    """测试工具定义格式"""
    tools = [
        SearchTool(),
        KnowledgeBaseTool(),
        WeatherTool(),
        CalculatorTool(),
        CurrentTimeTool(),
    ]

    for tool in tools:
        definition = tool.get_definition()

        # 检查必需字段
        assert "name" in definition
        assert "description" in definition
        assert "parameters" in definition

        # 检查参数格式
        params = definition["parameters"]
        assert "type" in params
        assert params["type"] == "object"
        assert "properties" in params


@pytest.mark.asyncio
async def test_dynamic_registry():
    """测试动态工具注册表"""
    registry = DynamicToolRegistry()

    # 测试工具列表
    tools = registry.list_tools()
    assert len(tools) == 5

    # 测试工具名称
    tool_names = registry.get_tool_names()
    assert "search" in tool_names
    assert "calculator" in tool_names
    assert "weather" in tool_names
    assert "knowledge_base" in tool_names
    assert "current_time" in tool_names

    # 测试工具执行
    result = await registry.execute_tool("calculator", {"expression": "10 + 20"})
    assert "30" in result

    # 测试工具信息
    tool_info = registry.get_tool_info("calculator")
    assert tool_info is not None
    assert tool_info["name"] == "calculator"

    # 测试不存在的工具
    with pytest.raises(ValueError):
        await registry.execute_tool("non_existent_tool", {})


@pytest.mark.asyncio
async def test_registry_get_definitions_for_llm():
    """测试获取 LLM 格式的工具定义"""
    registry = DynamicToolRegistry()

    definitions = registry.get_tool_definitions_for_llm()

    assert len(definitions) == 5

    for definition in definitions:
        assert "type" in definition
        assert definition["type"] == "function"
        assert "function" in definition

        func = definition["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func


@pytest.mark.asyncio
async def test_tool_execution_error_handling():
    """测试工具执行错误处理"""
    registry = DynamicToolRegistry()

    # 测试缺少必需参数（calculator 需要 expression）
    result = await registry.execute_tool("calculator", {})
    assert "错误" in result or "error" in result.lower()

    # 测试无效的数学表达式
    result = await registry.execute_tool("calculator", {"expression": "abc + def"})
    assert "错误" in result or "invalid" in result.lower()


@pytest.mark.asyncio
async def test_tools_description():
    """测试获取工具描述文本"""
    registry = DynamicToolRegistry()

    description = registry.get_tools_description()

    assert "search" in description
    assert "calculator" in description
    assert "weather" in description
    assert "knowledge_base" in description
    assert "current_time" in description


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_calculator_tool())
    asyncio.run(test_current_time_tool())
    asyncio.run(test_search_tool())
    asyncio.run(test_weather_tool())
    asyncio.run(test_knowledge_base_tool())
    test_tool_definitions()
    asyncio.run(test_dynamic_registry())
    asyncio.run(test_registry_get_definitions_for_llm())
    asyncio.run(test_tool_execution_error_handling())
    asyncio.run(test_tools_description())

    print("✅ All tests passed!")
