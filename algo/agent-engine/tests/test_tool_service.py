"""
Tool Service 单元测试
验证工具服务的核心功能，特别是安全性
"""

import sys
from pathlib import Path

import pytest

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tool_service import ToolService


class TestCalculatorTool:
    """计算器工具测试"""

    @pytest.fixture
    def tool_service(self):
        """创建工具服务实例"""
        return ToolService()

    def test_basic_arithmetic(self, tool_service):
        """测试基本算术运算"""
        # 加法
        result = tool_service._calculator_tool("2 + 2")
        assert result == "4"

        # 减法
        result = tool_service._calculator_tool("10 - 3")
        assert result == "7"

        # 乘法
        result = tool_service._calculator_tool("6 * 7")
        assert result == "42"

        # 除法
        result = tool_service._calculator_tool("15 / 3")
        assert result == "5.0"

    def test_complex_expressions(self, tool_service):
        """测试复杂表达式"""
        # 运算优先级
        result = tool_service._calculator_tool("2 + 3 * 4")
        assert result == "14"

        # 括号
        result = tool_service._calculator_tool("(2 + 3) * 4")
        assert result == "20"

        # 幂运算
        result = tool_service._calculator_tool("2 ** 3")
        assert result == "8"

        # 取模
        result = tool_service._calculator_tool("10 % 3")
        assert result == "1"

    def test_floating_point(self, tool_service):
        """测试浮点数运算"""
        result = tool_service._calculator_tool("3.14 * 2")
        assert float(result) == pytest.approx(6.28)

        result = tool_service._calculator_tool("10 / 3")
        assert float(result) == pytest.approx(3.333, rel=1e-2)

    def test_negative_numbers(self, tool_service):
        """测试负数"""
        result = tool_service._calculator_tool("-5 + 3")
        assert result == "-2"

        result = tool_service._calculator_tool("10 - (-5)")
        assert result == "15"

    def test_division_by_zero(self, tool_service):
        """测试除零错误"""
        result = tool_service._calculator_tool("10 / 0")
        assert "division by zero" in result.lower() or "error" in result.lower()

    def test_syntax_error(self, tool_service):
        """测试语法错误"""
        result = tool_service._calculator_tool("2 +")
        assert "error" in result.lower()

        result = tool_service._calculator_tool("((2 + 3)")
        assert "error" in result.lower()

    def test_security_injection_attempts(self, tool_service):
        """测试安全性 - 防止代码注入"""
        # 尝试导入模块
        result = tool_service._calculator_tool("__import__('os').system('ls')")
        assert "error" in result.lower()

        # 尝试访问内置函数
        result = tool_service._calculator_tool("eval('2+2')")
        assert "error" in result.lower()

        # 尝试访问私有属性
        result = tool_service._calculator_tool("().__class__.__bases__[0]")
        assert "error" in result.lower()

        # 尝试使用不支持的函数
        result = tool_service._calculator_tool("abs(-5)")
        assert "error" in result.lower()

    def test_malicious_expressions(self, tool_service):
        """测试恶意表达式"""
        # 尝试字符串
        result = tool_service._calculator_tool("'hello'")
        assert "error" in result.lower()

        # 尝试列表
        result = tool_service._calculator_tool("[1, 2, 3]")
        assert "error" in result.lower()

        # 尝试字典
        result = tool_service._calculator_tool("{'a': 1}")
        assert "error" in result.lower()


class TestToolRegistration:
    """工具注册测试"""

    @pytest.fixture
    def tool_service(self):
        """创建工具服务实例"""
        return ToolService()

    def test_builtin_tools_registered(self, tool_service):
        """测试内置工具已注册"""
        tools = tool_service.list_tools()
        tool_names = [t["name"] for t in tools]

        assert "calculator" in tool_names
        assert "knowledge_base" in tool_names
        assert "web_search" in tool_names

    def test_get_tool_info(self, tool_service):
        """测试获取工具信息"""
        info = tool_service.get_tool_info("calculator")
        assert info is not None
        assert info["name"] == "calculator"
        assert "description" in info
        assert "parameters" in info

    def test_get_nonexistent_tool(self, tool_service):
        """测试获取不存在的工具"""
        info = tool_service.get_tool_info("nonexistent_tool")
        assert info is None

    def test_custom_tool_registration(self, tool_service):
        """测试自定义工具注册"""
        def custom_tool(param1: str) -> str:
            return f"Custom: {param1}"

        tool_service.register_tool(
            name="custom_tool",
            description="A custom tool",
            function=custom_tool,
            parameters={"param1": {"type": "string"}},
            required_params=["param1"],
            category="custom"
        )

        tools = tool_service.list_tools()
        tool_names = [t["name"] for t in tools]
        assert "custom_tool" in tool_names


@pytest.mark.asyncio
class TestToolExecution:
    """工具执行测试"""

    @pytest.fixture
    def tool_service(self):
        """创建工具服务实例"""
        return ToolService()

    async def test_execute_calculator(self, tool_service):
        """测试执行计算器工具"""
        result = await tool_service.execute_tool(
            "calculator",
            {"expression": "2 + 2"}
        )
        assert result == "4"

    async def test_execute_missing_parameters(self, tool_service):
        """测试缺少必需参数"""
        with pytest.raises(ValueError, match="Missing required parameter"):
            await tool_service.execute_tool("calculator", {})

    async def test_execute_nonexistent_tool(self, tool_service):
        """测试执行不存在的工具"""
        with pytest.raises(ValueError, match="not found"):
            await tool_service.execute_tool(
                "nonexistent_tool",
                {"param": "value"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
