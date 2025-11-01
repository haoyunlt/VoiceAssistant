"""答案生成器 - 流式和非流式生成."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """答案生成器."""

    def __init__(
        self,
        llm_client: AsyncOpenAI,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ):
        """
        初始化答案生成器.

        Args:
            llm_client: OpenAI客户端
            model: 使用的模型
            temperature: 温度参数
            max_tokens: 最大生成token数
        """
        self.llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        生成答案 (非流式).

        Args:
            messages: OpenAI消息列表
            temperature: 温度参数 (覆盖默认值)
            max_tokens: 最大token数 (覆盖默认值)

        Returns:
            生成结果字典:
            - answer: 答案文本
            - model: 使用的模型
            - usage: Token使用情况
            - finish_reason: 完成原因
        """
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )

            choice = response.choices[0]
            usage = response.usage

            return {
                "answer": choice.message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "finish_reason": choice.finish_reason,
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            raise RuntimeError(f"Failed to generate answer: {e}") from e

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """
        生成答案 (流式).

        Args:
            messages: OpenAI消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Yields:
            答案文本片段
        """
        try:
            stream = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield f"\n\n[Error: {str(e)}]"

    async def generate_with_functions(
        self,
        messages: list[dict[str, str]],
        functions: list[dict[str, Any]],
        function_call: str | None = None,
    ) -> dict[str, Any]:
        """
        使用函数调用生成答案.

        Args:
            messages: OpenAI消息列表
            functions: 函数定义列表
            function_call: 强制调用的函数名 (可选)

        Returns:
            生成结果 (可能包含function_call)
        """
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "functions": functions,
                "temperature": self.temperature,
            }

            if function_call:
                kwargs["function_call"] = {"name": function_call}

            response = await self.llm_client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            result = {
                "model": response.model,
                "finish_reason": choice.finish_reason,
            }

            # 检查是否有函数调用
            if choice.message.function_call:
                result["function_call"] = {
                    "name": choice.message.function_call.name,
                    "arguments": json.loads(choice.message.function_call.arguments),
                }
            else:
                result["answer"] = choice.message.content

            if response.usage:
                result["usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return result

        except Exception as e:
            logger.error(f"Function calling generation failed: {e}")
            raise RuntimeError(f"Failed to generate with functions: {e}") from e

    async def batch_generate(
        self,
        messages_list: list[list[dict[str, str]]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        批量生成答案.

        Args:
            messages_list: 多个消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            生成结果列表
        """
        results = []

        for messages in messages_list:
            try:
                result = await self.generate(messages, temperature, max_tokens)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch generation item failed: {e}")
                results.append(
                    {
                        "answer": None,
                        "error": str(e),
                    }
                )

        return results
