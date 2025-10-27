"""
LLM Base - LLM 客户端基类

定义 LLM 客户端的通用接口
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息模型"""

    role: str = Field(..., description="角色: system/user/assistant/tool")
    content: str = Field(..., description="消息内容")
    name: Optional[str] = Field(None, description="消息发送者名称")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用")
    tool_call_id: Optional[str] = Field(None, description="工具调用 ID")


class CompletionResponse(BaseModel):
    """LLM 完成响应"""

    content: str = Field(..., description="生成的内容")
    model: str = Field(..., description="使用的模型")
    finish_reason: str = Field("stop", description="结束原因")
    usage: Optional[Dict[str, int]] = Field(None, description="Token 使用情况")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="工具调用")


class LLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化 LLM 客户端

        Args:
            model: 模型名称
            api_key: API 密钥
            base_url: API 基础 URL
            **kwargs: 其他参数
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.extra_params = kwargs

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        生成完成响应（非流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-2)
            max_tokens: 最大 token 数
            tools: 可用工具列表（OpenAI Function Calling 格式）
            **kwargs: 其他参数

        Returns:
            CompletionResponse 对象
        """
        pass

    @abstractmethod
    async def complete_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        生成完成响应（流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-2)
            max_tokens: 最大 token 数
            tools: 可用工具列表
            **kwargs: 其他参数

        Yields:
            生成的文本块
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        pass

    def format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        格式化消息为厂商特定格式

        Args:
            messages: Message 对象列表

        Returns:
            厂商特定格式的消息列表
        """
        return [msg.dict(exclude_none=True) for msg in messages]
