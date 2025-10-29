"""
动态工具注册系统

支持动态注册、注销和执行工具
"""

import logging
from typing import Any

from app.tools.real_tools import (
    CalculatorTool,
    CurrentTimeTool,
    KnowledgeBaseTool,
    SearchTool,
    WeatherTool,
)

logger = logging.getLogger(__name__)


class DynamicToolRegistry:
    """动态工具注册表"""

    def __init__(self):
        """初始化工具注册表"""
        self.tools: dict[str, Any] = {}
        self._init_builtin_tools()

        logger.info(
            f"DynamicToolRegistry initialized with {len(self.tools)} tools"
        )

    def _init_builtin_tools(self):
        """初始化内置工具"""
        # 实例化所有内置工具
        tool_instances = [
            SearchTool(),
            KnowledgeBaseTool(),
            WeatherTool(),
            CalculatorTool(),
            CurrentTimeTool(),
        ]

        for tool_instance in tool_instances:
            self.register(tool_instance)

    def register(self, tool_instance: Any):
        """
        注册工具

        Args:
            tool_instance: 工具实例，必须有 get_definition() 和 execute() 方法
        """
        try:
            definition = tool_instance.get_definition()
            tool_name = definition["name"]

            self.tools[tool_name] = {
                "instance": tool_instance,
                "definition": definition,
            }

            logger.info(f"✅ Registered tool: {tool_name}")

        except Exception as e:
            logger.error(f"Failed to register tool: {e}", exc_info=True)
            raise

    def unregister(self, tool_name: str):
        """
        注销工具

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.info(f"❌ Unregistered tool: {tool_name}")
        else:
            logger.warning(f"Tool '{tool_name}' not found, cannot unregister")

    async def execute_tool(
        self, tool_name: str, parameters: dict[str, Any]
    ) -> str:
        """
        执行工具

        Args:
            tool_name: 工具名称
            parameters: 工具参数

        Returns:
            执行结果（字符串格式）

        Raises:
            ValueError: 工具不存在
            Exception: 工具执行失败
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool_instance = self.tools[tool_name]["instance"]

        try:
            logger.info(f"Executing tool '{tool_name}' with parameters: {parameters}")

            # 执行工具（支持异步）
            result = await tool_instance.execute(**parameters)

            logger.info(f"Tool '{tool_name}' executed successfully")
            return str(result)

        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}", exc_info=True)
            return f"工具执行失败: {str(e)}"

    def list_tools(self) -> list[dict[str, Any]]:
        """
        列出所有工具

        Returns:
            工具定义列表
        """
        return [tool["definition"] for tool in self.tools.values()]

    def get_tool_definitions_for_llm(self) -> list[dict[str, Any]]:
        """
        获取 OpenAI Function Calling 格式的工具定义

        Returns:
            函数定义列表，格式为:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "...",
                        "description": "...",
                        "parameters": {...}
                    }
                },
                ...
            ]
        """
        return [
            {"type": "function", "function": tool["definition"]}
            for tool in self.tools.values()
        ]

    def get_tool_names(self) -> list[str]:
        """
        获取所有工具名称

        Returns:
            工具名称列表
        """
        return list(self.tools.keys())

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """
        获取工具信息

        Args:
            tool_name: 工具名称

        Returns:
            工具定义，如果不存在返回 None
        """
        tool = self.tools.get(tool_name)
        return tool["definition"] if tool else None

    def get_tools_description(self) -> str:
        """
        获取所有工具的文本描述

        Returns:
            工具描述文本
        """
        descriptions = []
        for tool_name, tool in self.tools.items():
            definition = tool["definition"]
            desc = f"- {tool_name}: {definition['description']}"

            # 添加参数信息
            params = definition.get("parameters", {}).get("properties", {})
            if params:
                param_list = []
                for param_name, param_info in params.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    param_list.append(f"{param_name} ({param_type}): {param_desc}")

                desc += "\n  参数: " + "; ".join(param_list)

            descriptions.append(desc)

        return "\n".join(descriptions)

    def clear_tools(self):
        """清空所有工具"""
        self.tools.clear()
        logger.warning("All tools cleared")

    def reload_builtin_tools(self):
        """重新加载内置工具"""
        self.clear_tools()
        self._init_builtin_tools()
        logger.info("Builtin tools reloaded")


# 全局工具注册表实例（单例）
_tool_registry_instance: DynamicToolRegistry | None = None


def get_tool_registry() -> DynamicToolRegistry:
    """
    获取全局工具注册表实例（单例模式）

    Returns:
        工具注册表实例
    """
    global _tool_registry_instance

    if _tool_registry_instance is None:
        _tool_registry_instance = DynamicToolRegistry()

    return _tool_registry_instance
