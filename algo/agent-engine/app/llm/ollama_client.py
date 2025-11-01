"""
Ollama LLM Client

Ollama 本地 LLM 客户端实现
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import CompletionResponse, LLMClient, Message

logger = logging.getLogger(__name__)


class OllamaClient(LLMClient):
    """Ollama 本地 LLM 客户端"""

    def __init__(
        self,
        model: str = "llama2",
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ):
        """
        初始化 Ollama 客户端

        Args:
            model: 模型名称（llama2, mistral, codellama, etc.）
            api_key: API 密钥（Ollama 通常不需要）
            base_url: Ollama 服务地址（默认 http://localhost:11434）
            **kwargs: 其他参数
        """
        super().__init__(model, api_key, base_url, **kwargs)

        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        logger.info(f"Ollama client initialized (model: {self.model}, url: {self.base_url})")

    async def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        _tools: list[dict[str, Any]] | None = None,
        **_kwargs,
    ) -> CompletionResponse:
        """
        生成完成响应（非流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-2)
            max_tokens: 最大 token 数
            tools: 可用工具列表（暂不支持）
            **kwargs: 其他参数

        Returns:
            CompletionResponse 对象
        """
        try:
            # 格式化消息
            formatted_messages = self.format_messages(messages)

            # 构建请求
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            # 调用 Ollama API
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            # 解析响应
            message = data.get("message", {})
            content = message.get("content", "")

            return CompletionResponse(
                content=content,
                model=self.model,
                finish_reason="stop",
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Ollama completion failed: HTTP {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Ollama completion failed: {e}", exc_info=True)
            raise

    async def complete_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        _tools: list[dict[str, Any]] | None = None,
        **_kwargs,
    ) -> AsyncIterator[str]:
        """
        生成完成响应（流式）

        Args:
            messages: 消息列表
            temperature: 温度参数 (0-2)
            max_tokens: 最大 token 数
            tools: 可用工具列表（暂不支持）
            **kwargs: 其他参数

        Yields:
            生成的文本块
        """
        try:
            # 格式化消息
            formatted_messages = self.format_messages(messages)

            # 构建请求
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            # 调用 Ollama API（流式）
            async with httpx.AsyncClient(timeout=120.0) as client:  # noqa: SIM117
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                message = data.get("message", {})
                                content = message.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            raise Exception(f"Ollama streaming failed: HTTP {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Ollama streaming completion failed: {e}", exc_info=True)
            raise

    def health_check(self) -> dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        try:
            # 尝试连接 Ollama
            import httpx

            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

                models = data.get("models", [])
                available_models = [m.get("name") for m in models]

                return {
                    "healthy": True,
                    "base_url": self.base_url,
                    "model": self.model,
                    "available_models": available_models,
                    "model_available": self.model in available_models,
                }

        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return {
                "healthy": False,
                "error": f"Cannot connect to Ollama: {str(e)}",
                "base_url": self.base_url,
            }
