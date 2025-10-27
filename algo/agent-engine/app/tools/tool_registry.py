"""
工具注册表
管理 Agent 可用的工具集合
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Tool:
    """工具类"""

    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        requires_auth: bool = False,
        timeout: int = 30
    ):
        """
        初始化工具

        Args:
            name: 工具名称
            description: 工具描述
            function: 工具函数
            parameters: 参数定义
            requires_auth: 是否需要认证
            timeout: 超时时间（秒）
        """
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
        self.requires_auth = requires_auth
        self.timeout = timeout

    def execute(self, **kwargs) -> Any:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        try:
            logger.info(f"Executing tool: {self.name}")
            result = self.function(**kwargs)
            logger.debug(f"Tool {self.name} result: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool {self.name} execution failed: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "requires_auth": self.requires_auth,
            "timeout": self.timeout
        }


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
        logger.info("Tool registry initialized")

    def _register_default_tools(self):
        """注册默认工具"""
        # 1. 搜索工具
        self.register_tool(
            name="search",
            description="Search for information on the internet",
            function=self._search_tool,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                    "required": True
                }
            }
        )

        # 2. 计算器工具
        self.register_tool(
            name="calculator",
            description="Perform mathematical calculations",
            function=self._calculator_tool,
            parameters={
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression",
                    "required": True
                }
            }
        )

        # 3. 知识库查询工具
        self.register_tool(
            name="knowledge_search",
            description="Search in the knowledge base",
            function=self._knowledge_search_tool,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                    "required": True
                },
                "tenant_id": {
                    "type": "string",
                    "description": "Tenant ID",
                    "required": True
                }
            }
        )

        # 4. 天气查询工具
        self.register_tool(
            name="weather",
            description="Get weather information for a location",
            function=self._weather_tool,
            parameters={
                "location": {
                    "type": "string",
                    "description": "Location name",
                    "required": True
                }
            }
        )

        # 5. 时间工具
        self.register_tool(
            name="current_time",
            description="Get current date and time",
            function=self._current_time_tool,
            parameters={}
        )

    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        requires_auth: bool = False,
        timeout: int = 30
    ):
        """
        注册工具

        Args:
            name: 工具名称
            description: 工具描述
            function: 工具函数
            parameters: 参数定义
            requires_auth: 是否需要认证
            timeout: 超时时间
        """
        tool = Tool(
            name=name,
            description=description,
            function=function,
            parameters=parameters,
            requires_auth=requires_auth,
            timeout=timeout
        )

        self.tools[name] = tool
        logger.info(f"Registered tool: {name}")

    def unregister_tool(self, name: str):
        """注销工具"""
        if name in self.tools:
            del self.tools[name]
            logger.info(f"Unregistered tool: {name}")

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self.tools.keys())

    def get_tools_description(self) -> str:
        """获取所有工具的描述"""
        descriptions = []
        for tool in self.tools.values():
            desc = f"- {tool.name}: {tool.description}"
            if tool.parameters:
                params = ", ".join([
                    f"{k} ({v.get('type', 'string')})"
                    for k, v in tool.parameters.items()
                ])
                desc += f"\n  Parameters: {params}"
            descriptions.append(desc)

        return "\n".join(descriptions)

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """
        执行工具

        Args:
            name: 工具名称
            args: 工具参数

        Returns:
            执行结果
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        # 验证参数
        self._validate_parameters(tool, args)

        # 执行工具
        return tool.execute(**args)

    def _validate_parameters(self, tool: Tool, args: Dict[str, Any]):
        """验证参数"""
        for param_name, param_def in tool.parameters.items():
            if param_def.get("required", False) and param_name not in args:
                raise ValueError(f"Required parameter '{param_name}' missing for tool '{tool.name}'")

    # 工具实现

    def _search_tool(self, query: str) -> str:
        """搜索工具（集成DuckDuckGo）"""
        logger.info(f"Searching for: {query}")
        try:
            import json

            import httpx

            # 使用 DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }

            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()

                    # 提取摘要或相关主题
                    result_parts = []

                    if data.get("Abstract"):
                        result_parts.append(f"摘要: {data['Abstract']}")

                    if data.get("RelatedTopics"):
                        topics = []
                        for topic in data["RelatedTopics"][:3]:
                            if isinstance(topic, dict) and "Text" in topic:
                                topics.append(topic["Text"])
                        if topics:
                            result_parts.append(f"相关主题: {'; '.join(topics)}")

                    if result_parts:
                        return "\n".join(result_parts)
                    else:
                        return f"未找到关于 '{query}' 的详细信息，建议使用更具体的搜索词。"
                else:
                    return f"搜索失败: HTTP {response.status_code}"
        except ImportError:
            logger.warning("httpx not installed, using mock results")
            return f"搜索结果 for '{query}': [需要安装 httpx 库以启用真实搜索]"
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"搜索出错: {str(e)}"

    def _calculator_tool(self, expression: str) -> str:
        """计算器工具"""
        try:
            # 安全计算（只允许数学表达式）
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Calculation error: {str(e)}"

    def _knowledge_search_tool(self, query: str, tenant_id: str) -> str:
        """知识库搜索工具（调用RAG服务）"""
        logger.info(f"Searching knowledge base: {query} (tenant: {tenant_id})")
        try:
            import os

            import httpx

            # 获取 RAG 服务地址
            rag_service_url = os.getenv("RAG_SERVICE_URL", "http://rag-engine:8004")

            # 调用 RAG 服务
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{rag_service_url}/retrieve",
                    json={
                        "query": query,
                        "tenant_id": tenant_id,
                        "top_k": 5
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])

                    if results:
                        formatted_results = []
                        for i, result in enumerate(results[:3], 1):
                            content = result.get("content", "")
                            score = result.get("score", 0)
                            formatted_results.append(f"{i}. (相关度: {score:.2f}) {content}")

                        return "知识库检索结果:\n" + "\n".join(formatted_results)
                    else:
                        return f"知识库中未找到与 '{query}' 相关的内容"
                else:
                    return f"知识库搜索失败: HTTP {response.status_code}"
        except ImportError:
            logger.warning("httpx not installed, using mock results")
            return f"知识库结果 for '{query}': [需要安装 httpx 库以启用真实搜索]"
        except Exception as e:
            logger.error(f"Knowledge search error: {e}")
            return f"知识库搜索出错: {str(e)}"

    def _weather_tool(self, location: str) -> str:
        """天气工具（集成 wttr.in API）"""
        logger.info(f"Getting weather for: {location}")
        try:
            import httpx

            # 使用 wttr.in API（免费，无需API key）
            url = f"https://wttr.in/{location}?format=j1"

            with httpx.Client(timeout=10) as client:
                response = client.get(url)
                if response.status_code == 200:
                    data = response.json()

                    current = data.get("current_condition", [{}])[0]

                    temp_c = current.get("temp_C", "N/A")
                    feels_like = current.get("FeelsLikeC", "N/A")
                    weather_desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                    humidity = current.get("humidity", "N/A")
                    wind_speed = current.get("windspeedKmph", "N/A")

                    result = (
                        f"天气信息 - {location}:\n"
                        f"天气: {weather_desc}\n"
                        f"温度: {temp_c}°C (体感: {feels_like}°C)\n"
                        f"湿度: {humidity}%\n"
                        f"风速: {wind_speed} km/h"
                    )

                    return result
                else:
                    return f"无法获取 '{location}' 的天气信息: HTTP {response.status_code}"
        except ImportError:
            logger.warning("httpx not installed, using mock results")
            return f"天气信息 for {location}: [需要安装 httpx 库以启用真实天气查询]"
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return f"天气查询出错: {str(e)}"

    def _current_time_tool(self) -> str:
        """当前时间工具"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_openai_functions(self) -> List[Dict[str, Any]]:
        """
        转换为 OpenAI Function Calling 格式

        Returns:
            函数定义列表
        """
        functions = []
        for tool in self.tools.values():
            func_def = {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": [
                        k for k, v in tool.parameters.items()
                        if v.get("required", False)
                    ]
                }
            }
            functions.append(func_def)

        return functions
