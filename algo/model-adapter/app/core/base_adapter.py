"""模型适配器基类."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class AdapterResponse:
    """适配器响应."""

    provider: str  # 提供商
    model: str  # 模型名称
    content: Optional[str] = None  # 生成的内容
    finish_reason: Optional[str] = None  # 完成原因
    usage: Dict[str, int] = field(default_factory=dict)  # Token使用情况
    function_call: Optional[Dict[str, Any]] = None  # 函数调用 (如果有)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据


@dataclass
class AdapterStreamChunk:
    """流式chunk."""

    provider: str
    model: str
    content: str
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAdapter(ABC):
    """模型适配器基类."""

    def __init__(self, provider: str):
        """
        初始化适配器.

        Args:
            provider: 提供商名称
        """
        self.provider = provider

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> AdapterResponse:
        """
        生成文本 (非流式).

        Args:
            model: 模型名称
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            适配器响应
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> AsyncIterator[AdapterStreamChunk]:
        """
        生成文本 (流式).

        Args:
            model: 模型名称
            messages: 消息列表
            **kwargs: 其他参数

        Yields:
            流式chunk
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        健康检查.

        Returns:
            是否健康
        """
        pass

