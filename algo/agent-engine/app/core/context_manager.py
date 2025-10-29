"""
上下文窗口管理模块 (MCP 风格)

智能管理 LLM 上下文窗口，优先级排序，动态截断。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """上下文组件类型"""

    SYSTEM_PROMPT = "system_prompt"  # 系统提示（必须）
    TASK = "task"  # 当前任务（必须）
    RECENT_MESSAGES = "recent_messages"  # 最近对话（高优）
    MEMORY = "memory"  # 长时记忆（中优）
    TOOL_DESCRIPTIONS = "tool_descriptions"  # 工具描述（按需）
    EXAMPLES = "examples"  # Few-shot 示例（低优）
    RETRIEVED_DOCS = "retrieved_docs"  # 检索文档（中优）


class Priority(Enum):
    """优先级"""

    CRITICAL = 100  # 关键（必须保留）
    HIGH = 75  # 高
    MEDIUM = 50  # 中
    LOW = 25  # 低


@dataclass
class ContextComponent:
    """上下文组件"""

    type: ComponentType
    content: str
    priority: Priority
    token_count: int
    metadata: dict[str, Any]


class ContextManager:
    """
    上下文窗口管理器 (MCP 风格)

    用法:
        manager = ContextManager(max_tokens=8000)

        # 添加组件
        manager.add_component("system_prompt", system_prompt, Priority.CRITICAL)
        manager.add_component("task", task, Priority.CRITICAL)
        manager.add_component("recent_messages", messages, Priority.HIGH)
        manager.add_component("memory", memory, Priority.MEDIUM)
        manager.add_component("tools", tools, Priority.MEDIUM)

        # 构建最终上下文（自动截断）
        context = manager.build_context()
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        model: str = "gpt-4",
        reserve_tokens: int = 1000,  # 为输出预留的 token
    ):
        """
        初始化上下文管理器

        Args:
            max_tokens: 最大 token 数
            model: 模型名称（用于 token 计算）
            reserve_tokens: 为输出预留的 token 数
        """
        self.max_tokens = max_tokens
        self.model = model
        self.reserve_tokens = reserve_tokens
        self.available_tokens = max_tokens - reserve_tokens

        # 组件列表
        self.components: list[ContextComponent] = []

        # Token 计数器
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found in tiktoken, using cl100k_base")
            self.encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(
            f"ContextManager initialized (max_tokens={max_tokens}, "
            f"available={self.available_tokens})"
        )

    def add_component(
        self,
        component_type: str,
        content: str,
        priority: Priority,
        metadata: dict | None = None,
    ):
        """
        添加上下文组件

        Args:
            component_type: 组件类型
            content: 内容
            priority: 优先级
            metadata: 元数据
        """
        token_count = self.count_tokens(content)

        component = ContextComponent(
            type=ComponentType(component_type),
            content=content,
            priority=priority,
            token_count=token_count,
            metadata=metadata or {},
        )

        self.components.append(component)
        logger.debug(
            f"Added component: {component_type} ({token_count} tokens, priority={priority.value})"
        )

    def build_context(self) -> str:
        """
        构建最终上下文

        Returns:
            构建的上下文文本
        """
        if not self.components:
            logger.warning("No components to build context")
            return ""

        # 按优先级排序
        sorted_components = sorted(
            self.components, key=lambda c: c.priority.value, reverse=True
        )

        # 贪心选择组件
        selected_components = []
        total_tokens = 0

        for component in sorted_components:
            if total_tokens + component.token_count <= self.available_tokens:
                selected_components.append(component)
                total_tokens += component.token_count
            elif component.priority == Priority.CRITICAL:
                # 关键组件必须包含，尝试截断
                logger.warning(
                    f"Critical component {component.type.value} exceeds budget, truncating"
                )
                truncated = self._truncate_component(
                    component, self.available_tokens - total_tokens
                )
                if truncated:
                    selected_components.append(truncated)
                    total_tokens += truncated.token_count
            else:
                logger.debug(
                    f"Component {component.type.value} skipped (insufficient tokens)"
                )

        # 按类型顺序重排（保持结构）
        selected_components.sort(
            key=lambda c: list(ComponentType).index(c.type)
        )

        # 构建最终文本
        context_parts = []
        for component in selected_components:
            context_parts.append(self._format_component(component))

        final_context = "\n\n".join(context_parts)

        logger.info(
            f"Built context: {len(selected_components)}/{len(self.components)} components, "
            f"{total_tokens}/{self.available_tokens} tokens"
        )

        return final_context

    def _truncate_component(
        self, component: ContextComponent, max_tokens: int
    ) -> ContextComponent | None:
        """截断组件"""
        if component.token_count <= max_tokens:
            return component

        if max_tokens <= 0:
            return None

        # 二分查找截断点
        tokens = self.encoding.encode(component.content)
        truncated_tokens = tokens[:max_tokens]
        truncated_content = self.encoding.decode(truncated_tokens)

        return ContextComponent(
            type=component.type,
            content=truncated_content + "... (truncated)",
            priority=component.priority,
            token_count=max_tokens,
            metadata=component.metadata,
        )

    def _format_component(self, component: ContextComponent) -> str:
        """格式化组件"""
        # 根据组件类型添加标题
        if component.type == ComponentType.SYSTEM_PROMPT:
            return f"# System\n{component.content}"
        elif component.type == ComponentType.TASK:
            return f"# Task\n{component.content}"
        elif component.type == ComponentType.RECENT_MESSAGES:
            return f"# Recent Conversation\n{component.content}"
        elif component.type == ComponentType.MEMORY:
            return f"# Memory\n{component.content}"
        elif component.type == ComponentType.TOOL_DESCRIPTIONS:
            return f"# Available Tools\n{component.content}"
        elif component.type == ComponentType.EXAMPLES:
            return f"# Examples\n{component.content}"
        elif component.type == ComponentType.RETRIEVED_DOCS:
            return f"# Retrieved Documents\n{component.content}"
        else:
            return component.content

    def count_tokens(self, text: str) -> int:
        """计算 token 数"""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # 粗略估计: 1 token ≈ 4 chars
            return len(text) // 4

    def clear(self):
        """清空所有组件"""
        self.components = []
        logger.debug("Cleared all components")

    def get_stats(self) -> dict:
        """获取统计信息"""
        total_tokens = sum(c.token_count for c in self.components)
        by_type = {}
        by_priority = {}

        for component in self.components:
            type_name = component.type.value
            priority_name = component.priority.name

            by_type[type_name] = by_type.get(type_name, 0) + component.token_count
            by_priority[priority_name] = by_priority.get(priority_name, 0) + component.token_count

        return {
            "total_components": len(self.components),
            "total_tokens": total_tokens,
            "available_tokens": self.available_tokens,
            "usage_ratio": total_tokens / self.available_tokens if self.available_tokens > 0 else 0.0,
            "by_type": by_type,
            "by_priority": by_priority,
        }


class DynamicToolLoader:
    """
    动态工具加载器

    根据任务只加载相关的工具描述。
    """

    def __init__(self, tool_registry: Any):
        """
        初始化动态工具加载器

        Args:
            tool_registry: 工具注册表
        """
        self.tool_registry = tool_registry
        logger.info("DynamicToolLoader initialized")

    async def select_tools(
        self, task: str, available_tools: list[str], max_tools: int = 5
    ) -> list[dict]:
        """
        选择任务相关的工具

        Args:
            task: 任务描述
            available_tools: 可用工具列表
            max_tools: 最大工具数

        Returns:
            选中的工具列表
        """
        # 简单启发式：关键词匹配
        task_lower = task.lower()
        scored_tools = []

        for tool_name in available_tools:
            tool_info = self.tool_registry.get_tool(tool_name)
            if not tool_info:
                continue

            description = tool_info.get("description", "").lower()

            # 计算相关性分数
            score = self._compute_relevance(task_lower, description)
            scored_tools.append((score, tool_name, tool_info))

        # 按分数排序，选择 top_k
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        selected = scored_tools[:max_tools]

        logger.info(
            f"Selected {len(selected)} tools for task (top scores: {[s[0] for s in selected[:3]]})"
        )

        return [tool_info for _, _, tool_info in selected]

    def _compute_relevance(self, task: str, tool_description: str) -> float:
        """计算任务与工具的相关性"""
        task_terms = set(task.split())
        desc_terms = set(tool_description.split())

        # Jaccard 相似度
        intersection = task_terms & desc_terms
        union = task_terms | desc_terms

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def format_tool_descriptions(
        self, tools: list[dict], compact: bool = False
    ) -> str:
        """
        格式化工具描述

        Args:
            tools: 工具列表
            compact: 是否使用紧凑格式（减少 token）

        Returns:
            格式化的工具描述
        """
        if compact:
            # 紧凑格式: 只包含名称和简短描述
            lines = []
            for tool in tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "")
                # 截断描述到第一句
                short_desc = desc.split(".")[0] if "." in desc else desc
                lines.append(f"- {name}: {short_desc}")
            return "\n".join(lines)
        else:
            # 完整格式: 包含参数和示例
            lines = []
            for tool in tools:
                name = tool.get("name", "unknown")
                desc = tool.get("description", "")
                params = tool.get("parameters", {})

                lines.append(f"## {name}")
                lines.append(f"Description: {desc}")
                if params:
                    lines.append(f"Parameters: {params}")
                lines.append("")

            return "\n".join(lines)

