"""工具服务 - 增强版with真实检索集成"""

import ast
import asyncio
import logging
import operator
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx  # type: ignore

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

logger = logging.getLogger(__name__)


class ToolService:
    """工具服务"""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}
        self.retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval-service:8012")
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # 计算器
        self.register_tool(
            name="calculator",
            description="Execute mathematical calculations. Input should be a valid mathematical expression.",
            function=self._calculator_tool,
            parameters={
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                }
            },
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
        function: Callable,
        parameters: dict[str, Any],
        required_params: list,
        category: str = "general",
    ) -> None:
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

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
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
        parameters: dict[str, Any],
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
        """
        计算器工具 - 使用AST安全求值
        避免eval()的安全风险
        """
        try:
            # 定义允许的操作符
            allowed_operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv,
                ast.Mod: operator.mod,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }

            def eval_node(node: ast.AST) -> Any:
                """递归求值AST节点"""
                if isinstance(node, ast.Constant):  # Python 3.8+
                    if isinstance(node.value, (int, float)):
                        return node.value
                    else:
                        raise ValueError(f"Unsupported constant type: {type(node.value)}")

                elif isinstance(node, ast.Num):  # Python 3.7 兼容
                    return node.n

                elif isinstance(node, ast.BinOp):
                    op_func = allowed_operators.get(type(node.op))
                    if not op_func:
                        raise ValueError(f"Unsupported binary operation: {type(node.op).__name__}")
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    return op_func(left, right)  # type: ignore

                elif isinstance(node, ast.UnaryOp):
                    op_func = allowed_operators.get(type(node.op))
                    if not op_func:
                        raise ValueError(f"Unsupported unary operation: {type(node.op).__name__}")
                    operand = eval_node(node.operand)
                    return op_func(operand)  # type: ignore

                else:
                    raise ValueError(f"Unsupported expression type: {type(node).__name__}")

            # 解析表达式
            tree = ast.parse(expression, mode="eval")
            result = eval_node(tree.body)

            # 检查结果是否有效
            if not isinstance(result, (int, float)):
                return f"Error: Result must be a number, got {type(result)}"

            return str(result)

        except SyntaxError as e:
            logger.warning(f"Calculator syntax error: {e}")
            return f"Syntax error: {str(e)}"
        except ZeroDivisionError:
            logger.warning("Calculator division by zero")
            return "Error: Division by zero"
        except ValueError as e:
            logger.warning(f"Calculator value error: {e}")
            return f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Calculator unexpected error: {e}", exc_info=True)
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
        互联网搜索工具
        集成真实搜索 API (DuckDuckGo / SerpAPI)
        """
        import os

        logger.info(f"Web search: {query}")

        try:
            # 优先使用 SerpAPI（如果配置了）
            if os.getenv("SERPAPI_KEY"):
                return await self._search_with_serpapi(query)

            # 备选：DuckDuckGo
            return await self._search_with_duckduckgo(query)

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"搜索失败: {str(e)}"

    async def _search_with_serpapi(self, query: str) -> str:
        """使用 SerpAPI 搜索"""
        import os

        import httpx

        api_key = os.getenv("SERPAPI_KEY")
        url = "https://serpapi.com/search"

        params = {"engine": "google", "q": query, "api_key": api_key, "num": 5}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()

        # 提取搜索结果
        snippets = []
        for item in result.get("organic_results", [])[:5]:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            snippets.append(f"**{title}**\n{snippet}\nURL: {link}")

        return "\n\n".join(snippets) if snippets else "未找到相关结果"

    async def _search_with_duckduckgo(self, query: str) -> str:
        """使用 DuckDuckGo 搜索"""
        try:
            import asyncio

            from duckduckgo_search import DDGS

            # DuckDuckGo 搜索（在线程池中执行）
            def search() -> list[dict[str, str]]:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=5))

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, search)

            if not results:
                return "未找到相关结果"

            snippets = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                snippets.append(f"**{title}**\n{body}\nURL: {href}")

            return "\n\n".join(snippets)

        except ImportError:
            return "DuckDuckGo 搜索模块未安装。请运行: pip install duckduckgo-search"
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return f"搜索失败: {str(e)}"
