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
        """搜索工具（模拟）"""
        logger.info(f"Searching for: {query}")
        # TODO: 实现真实的搜索功能
        return f"Search results for '{query}': [Mock results]"

    def _calculator_tool(self, expression: str) -> str:
        """计算器工具"""
        try:
            # 安全计算（只允许数学表达式）
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as e:
            return f"Calculation error: {str(e)}"

    def _knowledge_search_tool(self, query: str, tenant_id: str) -> str:
        """知识库搜索工具（模拟）"""
        logger.info(f"Searching knowledge base: {query} (tenant: {tenant_id})")
        # TODO: 实现真实的知识库搜索
        return f"Knowledge base results for '{query}': [Mock results]"

    def _weather_tool(self, location: str) -> str:
        """天气工具（模拟）"""
        logger.info(f"Getting weather for: {location}")
        # TODO: 实现真实的天气API调用
        return f"Weather in {location}: Sunny, 25°C"

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
