"""
Tool Registry - 工具注册表
"""

import logging

from app.core.tools.builtin_tools import *

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools = {}
        logger.info("Tool registry created")

    async def initialize(self):
        """初始化：注册内置工具"""
        self._register_builtin_tools()
        logger.info(f"Tool registry initialized with {len(self.tools)} tools")

    def _register_builtin_tools(self):
        """注册内置工具"""
        tools = [
            SearchTool(),
            CalculatorTool(),
            WebScraperTool(),
            FileReaderTool(),
        ]

        for tool in tools:
            self.register_tool(tool)

    def register_tool(self, tool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def list_tools(self) -> list[dict]:
        """列出所有工具"""
        return [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in self.tools.items()
        ]

    async def execute_tool(self, tool_name: str, tool_input: str) -> str:
        """执行工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        return await tool.run(tool_input)
