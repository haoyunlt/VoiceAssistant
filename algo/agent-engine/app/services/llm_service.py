"""LLM服务"""

import logging
from typing import Any

import httpx  # type: ignore

from app.core.config import AgentConfig

logger = logging.getLogger(__name__)


class LLMService:
    """大语言模型服务"""

    def __init__(self) -> None:
        self.api_key = AgentConfig.llm_api_key
        self.api_base = AgentConfig.llm_api_base
        self.default_model = AgentConfig.llm_model
        self.timeout = AgentConfig.llm_timeout

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        调用LLM Chat接口

        Args:
            messages: 对话历史
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            LLM响应
        """
        try:
            model = model or self.default_model
            max_tokens = max_tokens or AgentConfig.llm_max_tokens

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )

                response.raise_for_status()
                data = response.json()

                # 提取响应内容
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")

                return {
                    "content": content,
                    "model": data.get("model"),
                    "usage": data.get("usage", {}),
                }

        except httpx.HTTPError as e:
            logger.error(f"LLM API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM service error: {e}")
            raise

    async def completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        调用LLM Completion接口（简化版）

        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            生成的文本
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.chat(messages, model, temperature, max_tokens)
        return response.get("content", "") if isinstance(response.get("content"), str) else ""
