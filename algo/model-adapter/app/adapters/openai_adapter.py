"""OpenAI模型适配器."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from app.core.base_adapter import AdapterResponse, AdapterStreamChunk, BaseAdapter
from app.core.resilience import with_resilience, StreamErrorHandler

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """OpenAI API适配器."""

    def __init__(self, api_key: str, base_url: str | None = None):
        """
        初始化OpenAI适配器.

        Args:
            api_key: API密钥
            base_url: 自定义base URL (可选)
        """
        super().__init__(provider="openai")
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @with_resilience(
        provider_name="openai",
        max_attempts=3,
        timeout=60.0,
        fail_max=5,
        breaker_timeout=30,
        retry_exceptions=(OpenAIError, TimeoutError),
    )
    async def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: list[str] | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """
        生成文本 (非流式).

        自动重试 (3次) + 熔断器保护 + 60s超时

        Args:
            model: 模型名称 (如 gpt-3.5-turbo)
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            top_p: 采样概率
            frequency_penalty: 频率惩罚
            presence_penalty: 存在惩罚
            stop: 停止序列
            **kwargs: 其他参数

        Returns:
            适配器响应

        Raises:
            RuntimeError: OpenAI API错误或熔断器打开
        """
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop,
                **kwargs,
            )

            choice = response.choices[0]
            usage = response.usage

            return AdapterResponse(
                provider=self.provider,
                model=response.model,
                content=choice.message.content,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
                metadata={
                    "id": response.id,
                    "created": response.created,
                    "system_fingerprint": getattr(response, "system_fingerprint", None),
                },
            )

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}")

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

        自动错误处理 + SSE格式错误事件

        Args:
            model: 模型名称
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 其他参数

        Yields:
            流式chunk或错误事件
        """
        async def _internal_stream():
            """内部流式生成器."""
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    yield AdapterStreamChunk(
                        provider=self.provider,
                        model=chunk.model,
                        content=delta.content,
                        finish_reason=choice.finish_reason,
                        metadata={"id": chunk.id},
                    )

        # 使用StreamErrorHandler包装，增加错误处理和心跳
        async for event in StreamErrorHandler.wrap_stream_with_error_handling(
            _internal_stream(),
            provider=self.provider,
            model=model,
        ):
            yield event

    async def generate_with_functions(
        self,
        model: str,
        messages: list[dict[str, str]],
        functions: list[dict[str, Any]],
        function_call: str | None = None,
        **kwargs,
    ) -> AdapterResponse:
        """
        使用函数调用生成.

        Args:
            model: 模型名称
            messages: 消息列表
            functions: 函数定义列表
            function_call: 强制调用的函数 (可选)
            **kwargs: 其他参数

        Returns:
            适配器响应 (可能包含function_call)
        """
        try:
            request_kwargs = {
                "model": model,
                "messages": messages,
                "functions": functions,
                **kwargs,
            }

            if function_call:
                request_kwargs["function_call"] = {"name": function_call}

            response = await self.client.chat.completions.create(**request_kwargs)

            choice = response.choices[0]
            usage = response.usage

            # 检查是否有函数调用
            function_call_data = None
            if hasattr(choice.message, "function_call") and choice.message.function_call:
                function_call_data = {
                    "name": choice.message.function_call.name,
                    "arguments": choice.message.function_call.arguments,
                }

            return AdapterResponse(
                provider=self.provider,
                model=response.model,
                content=choice.message.content,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
                function_call=function_call_data,
                metadata={"id": response.id},
            )

        except OpenAIError as e:
            logger.error(f"OpenAI function calling error: {e}")
            raise RuntimeError(f"OpenAI function calling error: {e}")

    async def create_embedding(
        self,
        model: str,
        input_text: str | list[str],
        **kwargs,
    ) -> dict[str, Any]:
        """
        创建文本嵌入.

        Args:
            model: 嵌入模型名称 (如 text-embedding-ada-002)
            input_text: 输入文本或文本列表
            **kwargs: 其他参数

        Returns:
            嵌入结果
        """
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=input_text,
                **kwargs,
            )

            return {
                "provider": self.provider,
                "model": response.model,
                "embeddings": [data.embedding for data in response.data],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "metadata": {"id": getattr(response, "id", None)},
            }

        except OpenAIError as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise RuntimeError(f"OpenAI embedding error: {e}")

    async def health_check(self) -> bool:
        """
        健康检查.

        Returns:
            是否健康
        """
        try:
            # 尝试列出模型
            await self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
