"""
OpenAI LLM Client

OpenAI API 客户端实现
"""

import os
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None

import logging
from app.llm.base import CompletionResponse, LLMClient, Message

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    """OpenAI LLM 客户端"""

    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化 OpenAI 客户端

        Args:
            model: 模型名称（gpt-4-turbo-preview, gpt-3.5-turbo, etc.）
            api_key: OpenAI API 密钥
            base_url: API 基础 URL（可选，用于代理）
            organization: Organization ID（可选）
            **kwargs: 其他参数
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI SDK not installed. "
                "Install it with: pip install openai"
            )

        super().__init__(model, api_key, base_url, **kwargs)

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.organization = organization or os.getenv("OPENAI_ORG_ID")

        if not self.api_key:
            logger.warning(
                "OpenAI API key not provided. "
                "Set OPENAI_API_KEY environment variable or pass it to constructor."
            )

        # 初始化客户端
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        if self.organization:
            client_kwargs["organization"] = self.organization

        self.client = AsyncOpenAI(**client_kwargs) if self.api_key else None

        logger.info(f"OpenAI client initialized (model: {self.model})")

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
        if not self.client:
            raise ValueError("OpenAI client not initialized (missing API key)")

        try:
            # 格式化消息
            formatted_messages = self.format_messages(messages)

            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }

            # 添加工具（如果提供）
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"

            # 调用 OpenAI API
            response = await self.client.chat.completions.create(**request_params)

            # 解析响应
            choice = response.choices[0]
            message = choice.message

            # 提取内容
            content = message.content or ""

            # 提取工具调用
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]

            # 构建响应
            return CompletionResponse(
                content=content,
                model=response.model,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                if response.usage
                else None,
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.error(f"OpenAI completion failed: {e}", exc_info=True)
            raise

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
        if not self.client:
            raise ValueError("OpenAI client not initialized (missing API key)")

        try:
            # 格式化消息
            formatted_messages = self.format_messages(messages)

            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **kwargs,
            }

            # 添加工具（如果提供）
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"

            # 调用 OpenAI API（流式）
            stream = await self.client.chat.completions.create(**request_params)

            # 迭代流式响应
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as e:
            logger.error(f"OpenAI streaming completion failed: {e}", exc_info=True)
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not OPENAI_AVAILABLE:
            return {
                "healthy": False,
                "error": "OpenAI SDK not installed",
            }

        if not self.api_key:
            return {
                "healthy": False,
                "error": "OpenAI API key not configured",
            }

        return {
            "healthy": True,
            "model": self.model,
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
        }
