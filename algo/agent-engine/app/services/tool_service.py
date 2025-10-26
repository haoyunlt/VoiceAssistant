"""工具服务 - 管理和执行工具"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from app.models.agent import ToolDefinition

logger = logging.getLogger(__name__)


class ToolService:
    """工具服务"""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具"""
        # 计算器工具
        self.register_tool(
            name="calculator",
            description="Perform mathematical calculations",
            function=self._calculator_tool,
            parameters={
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                }
            },
            required_params=["expression"],
        )

        # 搜索工具（示例）
        self.register_tool(
            name="search",
            description="Search for information on the internet",
            function=self._search_tool,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                }
            },
            required_params=["query"],
        )

        # 知识库查询工具（示例）
        self.register_tool(
            name="knowledge_base",
            description="Query knowledge base for relevant information",
            function=self._knowledge_base_tool,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Query to search in knowledge base",
                }
            },
            required_params=["query"],
        )

    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        required_params: List[str],
        category: str = "general",
    ):
        """注册工具"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "function": function,
            "parameters": parameters,
            "required_params": required_params,
            "category": category,
        }
        logger.info(f"Registered tool: {name}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
                "required_params": tool["required_params"],
                "category": tool["category"],
            }
            for tool in self.tools.values()
        ]

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        tool = self.tools.get(tool_name)
        if not tool:
            return None

        return {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "required_params": tool["required_params"],
            "category": tool["category"],
        }

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """执行工具"""
        tool = self.tools.get(tool_name)

        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        # 验证必需参数
        for param in tool["required_params"]:
            if param not in parameters:
                raise ValueError(f"Missing required parameter: {param}")

        # 执行工具函数
        function = tool["function"]

        try:
            # 如果是协程函数
            if asyncio.iscoroutinefunction(function):
                result = await function(**parameters)
            else:
                result = function(**parameters)

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            raise

    # ==================== 内置工具实现 ====================

    def _calculator_tool(self, expression: str) -> str:
        """计算器工具"""
        try:
            # 注意：实际应该使用更安全的表达式求值
            # 这里仅为演示
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Calculation error: {str(e)}"

    async def _search_tool(self, query: str) -> str:
        """搜索工具（示例实现）"""
        # 实际应该调用真实的搜索API
        logger.info(f"Searching for: {query}")
        return f"Search results for '{query}': [Mock result - implement real search API]"

    async def _knowledge_base_tool(self, query: str) -> str:
        """知识库查询工具（示例实现）"""
        # 实际应该调用知识库服务
        logger.info(f"Querying knowledge base: {query}")
        return f"Knowledge base results for '{query}': [Mock result - implement real KB query]"
