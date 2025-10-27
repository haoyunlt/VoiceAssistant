"""
统一LLM调用客户端 - 通过model-adapter调用
所有AI引擎必须使用此客户端，禁止直连OpenAI/Anthropic等
"""

import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class UnifiedLLMClient:
    """统一LLM客户端 - 通过model-adapter调用"""

    def __init__(
        self,
        model_adapter_url: Optional[str] = None,
        timeout: int = 60,
        default_model: str = "gpt-3.5-turbo",
    ):
        """
        初始化统一LLM客户端

        Args:
            model_adapter_url: model-adapter服务地址
            timeout: 请求超时时间（秒）
            default_model: 默认模型名称
        """
        self.base_url = (
            model_adapter_url
            or os.getenv("MODEL_ADAPTER_URL", "http://model-adapter:8005")
        ).rstrip("/")
        self.timeout = timeout
        self.default_model = default_model

        logger.info(
            f"UnifiedLLMClient initialized: base_url={self.base_url}, model={default_model}"
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        聊天接口（非流式）

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称（默认使用default_model）
            temperature: 温度参数
            max_tokens: 最大token数
            stream: 是否流式（此方法不支持）
            **kwargs: 其他参数

        Returns:
            响应字典 {"content": "...", "model": "...", "usage": {...}}
        """
        if stream:
            raise ValueError("Use chat_stream() for streaming responses")

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            **kwargs,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/chat/completions", json=payload
                )
                response.raise_for_status()
                data = response.json()

                # 统一返回格式
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "model": data.get("model", model),
                    "usage": data.get("usage", {}),
                    "finish_reason": data["choices"][0].get("finish_reason"),
                }

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"LLM request failed: {e.response.text}")
        except httpx.TimeoutException:
            logger.error(f"LLM request timeout after {self.timeout}s")
            raise RuntimeError(f"LLM request timeout")
        except Exception as e:
            logger.error(f"Unexpected error in LLM request: {e}", exc_info=True)
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        聊天接口（流式）

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数

        Yields:
            流式文本块
        """
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/v1/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix

                            if data_str == "[DONE]":
                                break

                            try:
                                import json

                                data = json.loads(data_str)
                                delta = data["choices"][0]["delta"]

                                if "content" in delta:
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_str}")
                                continue

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM stream error: {e.response.status_code}")
            raise RuntimeError(f"LLM stream failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error in LLM stream: {e}", exc_info=True)
            raise

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        简单生成接口（便捷方法）

        Args:
            prompt: 提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数

        Returns:
            生成的文本
        """
        messages = [{"role": "user", "content": prompt}]

        result = await self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        return result["content"]

    async def create_embedding(
        self, input_texts: List[str], model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """
        创建文本向量

        Args:
            input_texts: 输入文本列表
            model: embedding模型名称

        Returns:
            向量列表
        """
        payload = {"model": model, "input": input_texts}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/embedding/create", json=payload
                )
                response.raise_for_status()
                data = response.json()

                # 提取embeddings
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings

        except httpx.HTTPStatusError as e:
            logger.error(f"Embedding API error: {e.response.status_code}")
            raise RuntimeError(f"Embedding request failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error in embedding request: {e}", exc_info=True)
            raise


# 全局单例（可选）
_default_client: Optional[UnifiedLLMClient] = None


def get_default_client() -> UnifiedLLMClient:
    """获取默认的LLM客户端单例"""
    global _default_client
    if _default_client is None:
        _default_client = UnifiedLLMClient()
    return _default_client
