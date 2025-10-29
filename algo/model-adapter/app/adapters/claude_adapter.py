"""Claude (Anthropic)模型适配器."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AnthropicError, AsyncAnthropic

from app.core.base_adapter import AdapterResponse, AdapterStreamChunk, BaseAdapter

logger = logging.getLogger(__name__)


class ClaudeAdapter(BaseAdapter):
    """Claude API适配器."""

    def __init__(self, api_key: str):
        """
        初始化Claude适配器.

        Args:
            api_key: API密钥
        """
        super().__init__(provider="claude")
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 1.0,
        top_k: int = -1,
        stop_sequences: list[str] | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """
        生成文本 (非流式).

        Args:
            model: 模型名称 (如 claude-3-sonnet-20240229)
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            top_p: 采样概率
            top_k: Top-K采样
            stop_sequences: 停止序列
            **kwargs: 其他参数

        Returns:
            适配器响应
        """
        try:
            # 转换消息格式 (Claude需要system消息分离)
            system_prompt, formatted_messages = self._format_messages(messages)

            request_kwargs = {
                "model": model,
                "messages": formatted_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                **kwargs,
            }

            if system_prompt:
                request_kwargs["system"] = system_prompt

            if top_k > 0:
                request_kwargs["top_k"] = top_k

            if stop_sequences:
                request_kwargs["stop_sequences"] = stop_sequences

            response = await self.client.messages.create(**request_kwargs)

            # 提取内容
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            return AdapterResponse(
                provider=self.provider,
                model=response.model,
                content=content,
                finish_reason=response.stop_reason,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                metadata={
                    "id": response.id,
                    "type": response.type,
                    "role": response.role,
                },
            )

        except AnthropicError as e:
            logger.error(f"Claude API error: {e}")
            raise RuntimeError(f"Claude API error: {e}")

    async def generate_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> AsyncIterator[AdapterStreamChunk]:
        """
        生成文本 (流式).

        Args:
            model: 模型名称
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 其他参数

        Yields:
            流式chunk
        """
        try:
            # 转换消息格式
            system_prompt, formatted_messages = self._format_messages(messages)

            request_kwargs = {
                "model": model,
                "messages": formatted_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                **kwargs,
            }

            if system_prompt:
                request_kwargs["system"] = system_prompt

            async with self.client.messages.stream(**request_kwargs) as stream:
                async for event in stream:
                    # 处理不同类型的事件
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield AdapterStreamChunk(
                                    provider=self.provider,
                                    model=model,
                                    content=event.delta.text,
                                    finish_reason=None,
                                    metadata={"event_type": event.type},
                                )
                        elif event.type == "message_stop":
                            yield AdapterStreamChunk(
                                provider=self.provider,
                                model=model,
                                content="",
                                finish_reason="end_turn",
                                metadata={"event_type": event.type},
                            )

        except AnthropicError as e:
            logger.error(f"Claude streaming error: {e}")
            raise RuntimeError(f"Claude streaming error: {e}")

    def _format_messages(self, messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, str]]]:
        """
        格式化消息为Claude格式.

        Claude需要将system消息分离出来。

        Args:
            messages: OpenAI格式的消息列表

        Returns:
            (system_prompt, formatted_messages)
        """
        system_prompt = None
        formatted_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                # 提取system消息
                if system_prompt is None:
                    system_prompt = content
                else:
                    system_prompt += "\n\n" + content
            else:
                # 保留user和assistant消息
                formatted_messages.append({
                    "role": role,
                    "content": content,
                })

        return system_prompt, formatted_messages

    async def generate_with_vision(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs,
    ) -> AdapterResponse:
        """
        使用视觉理解生成.

        Claude 3支持图像输入。

        Args:
            model: 模型名称
            messages: 消息列表 (可包含图像)
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 其他参数

        Returns:
            适配器响应
        """
        try:
            # 转换消息格式
            system_prompt, formatted_messages = self._format_messages_with_images(messages)

            request_kwargs = {
                "model": model,
                "messages": formatted_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs,
            }

            if system_prompt:
                request_kwargs["system"] = system_prompt

            response = await self.client.messages.create(**request_kwargs)

            # 提取内容
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            return AdapterResponse(
                provider=self.provider,
                model=response.model,
                content=content,
                finish_reason=response.stop_reason,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                metadata={"id": response.id, "has_vision": True},
            )

        except AnthropicError as e:
            logger.error(f"Claude vision error: {e}")
            raise RuntimeError(f"Claude vision error: {e}")

    def _format_messages_with_images(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        格式化包含图像的消息.

        Args:
            messages: 消息列表 (可能包含图像)

        Returns:
            (system_prompt, formatted_messages)
        """
        system_prompt = None
        formatted_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if system_prompt is None:
                    system_prompt = content
                else:
                    system_prompt += "\n\n" + content
            else:
                # 处理可能包含图像的内容
                if isinstance(content, str):
                    formatted_messages.append({
                        "role": role,
                        "content": content,
                    })
                elif isinstance(content, list):
                    # 多模态内容
                    formatted_messages.append({
                        "role": role,
                        "content": content,
                    })

        return system_prompt, formatted_messages

    async def health_check(self) -> bool:
        """
        健康检查.

        Returns:
            是否健康
        """
        try:
            # 尝试发送一个最小请求
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",  # 使用最便宜的模型
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return response is not None
        except Exception as e:
            logger.warning(f"Claude health check failed: {e}")
            return False
