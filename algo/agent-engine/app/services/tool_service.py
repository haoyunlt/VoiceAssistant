"""工具服务 - 增强版with真实检索集成"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

import httpx

logger = logging.getLogger(__name__)


class ToolService:
    """工具服务"""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval-service:8012")
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具"""
        # 计算器
        self.register_tool(
            name="calculator",
            description="Execute mathematical calculations. Input should be a valid mathematical expression.",
            function=self._calculator_tool,
            parameters={"expression": {"type": "string", "description": "Mathematical expression to evaluate"}},
            required_params=["expression"],
            category="computation",
        )

        # 知识库搜索（真实实现）
        self.register_tool(
            name="knowledge_base",
            description="Search the knowledge base for relevant information. Use this when you need to find documents or answers from the knowledge base.",
            function=self._knowledge_base_tool,
            parameters={"query": {"type": "string", "description": "Search query"}},
            required_params=["query"],
            category="retrieval",
        )

        # 互联网搜索（示例 - 需要接入真实API）
        self.register_tool(
            name="web_search",
            description="Search the internet for information. Use this for current events or information not in the knowledge base.",
            function=self._web_search_tool,
            parameters={"query": {"type": "string", "description": "Search query"}},
            required_params=["query"],
            category="search",
        )

    def register_tool(
        self,
        name: str,
        description: str,
        function: callable,
        parameters: Dict[str, Any],
        required_params: list,
        category: str = "general",
    ):
        """
        注册工具

        Args:
            name: 工具名称
            description: 工具描述
            function: 工具函数
            parameters: 参数定义
            required_params: 必需参数列表
            category: 工具分类
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "function": function,
            "parameters": parameters,
            "required_params": required_params,
            "category": category,
        }
        logger.info(f"Tool registered: {name} ({category})")

    def list_tools(self) -> list:
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
            # 安全的数学表达式求值
            # 只允许基本数学操作
            allowed_chars = set("0123456789+-*/().% ")
            if not all(c in allowed_chars for c in expression):
                return "Error: Invalid characters in expression. Only numbers and basic operators are allowed."

            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Calculation error: {str(e)}"

    async def _knowledge_base_tool(self, query: str) -> str:
        """
        知识库查询工具（真实实现）

        通过retrieval-service进行混合检索
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.retrieval_url}/api/v1/retrieval/hybrid",
                    json={
                        "query": query,
                        "top_k": 5,
                        "rerank": True,
                        "tenant_id": os.getenv("DEFAULT_TENANT_ID", "default"),
                    },
                )

                if response.status_code == 404:
                    logger.warning(f"Retrieval service not available at {self.retrieval_url}")
                    return "Knowledge base is currently unavailable. Please try again later."

                response.raise_for_status()
                results = response.json()

                documents = results.get("documents", [])

                if not documents:
                    return f"No relevant information found for query: '{query}'"

                # 格式化为Agent可读的文本
                formatted = f"Found {len(documents)} relevant documents:\n\n"
                for i, doc in enumerate(documents[:3], 1):
                    content = doc.get("content", "")[:200]
                    score = doc.get("score", 0.0)
                    formatted += f"{i}. [Score: {score:.2f}] {content}...\n\n"

                return formatted

        except httpx.ConnectError:
            logger.error(f"Cannot connect to retrieval service at {self.retrieval_url}")
            return "Knowledge base service is unavailable. Please check if the retrieval service is running."
        except httpx.HTTPError as e:
            logger.error(f"Knowledge base query failed: {e}")
            return f"Error querying knowledge base: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in knowledge base tool: {e}", exc_info=True)
            return f"Unexpected error: {str(e)}"

    async def _web_search_tool(self, query: str) -> str:
        """
        互联网搜索工具（示例实现）

        TODO: 接入真实搜索API（如Google、Bing、DuckDuckGo等）
        """
        logger.info(f"Web search (mock): {query}")

        # 示例实现 - 返回Mock结果
        return f"""Web search results for '{query}':

1. [Example Result 1] This is a mock search result. In production, this would call a real search API.

2. [Example Result 2] You can integrate with Google Custom Search, Bing API, or other search services.

3. [Example Result 3] Consider using Serper API, SerpAPI, or similar services for production.

Note: This is a placeholder. Implement real search API integration for production use."""
