"""智谱AI模型适配器."""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from ..core.base_adapter import AdapterResponse, AdapterStreamChunk, BaseAdapter

logger = logging.getLogger(__name__)


class ZhipuAdapter(BaseAdapter):
    """智谱AI API适配器."""

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4"):
        """
        初始化智谱AI适配器.

        Args:
            api_key: API密钥
            base_url: API基础URL
        """
        super().__init__(provider="zhipu")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        top_p: float = 0.7,
        **kwargs,
    ) -> AdapterResponse:
        """
        生成文本 (非流式).

        Args:
            model: 模型名称 (如 glm-4)
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            top_p: 采样概率
            **kwargs: 其他参数

        Returns:
            适配器响应
        """
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                **kwargs,
            }

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            # 提取响应
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return AdapterResponse(
                provider=self.provider,
                model=data.get("model", model),
                content=choice["message"]["content"],
                finish_reason=choice.get("finish_reason"),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                metadata={
                    "id": data.get("id"),
                    "created": data.get("created"),
                },
            )

        except httpx.HTTPError as e:
            logger.error(f"Zhipu API HTTP error: {e}")
            raise RuntimeError(f"Zhipu API HTTP error: {e}")
        except Exception as e:
            logger.error(f"Zhipu API error: {e}")
            raise RuntimeError(f"Zhipu API error: {e}")

    async def generate_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
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
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **kwargs,
            }

            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    # SSE格式: data: {...}
                    if line.startswith("data: "):
                        line_data = line[6:]

                        # 检查结束标记
                        if line_data == "[DONE]":
                            break

                        try:
                            import json
                            data = json.loads(line_data)

                            if "choices" in data and data["choices"]:
                                choice = data["choices"][0]
                                delta = choice.get("delta", {})

                                if "content" in delta and delta["content"]:
                                    yield AdapterStreamChunk(
                                        provider=self.provider,
                                        model=data.get("model", model),
                                        content=delta["content"],
                                        finish_reason=choice.get("finish_reason"),
                                        metadata={"id": data.get("id")},
                                    )

                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode JSON: {line_data}")
                            continue

        except httpx.HTTPError as e:
            logger.error(f"Zhipu streaming HTTP error: {e}")
            raise RuntimeError(f"Zhipu streaming HTTP error: {e}")
        except Exception as e:
            logger.error(f"Zhipu streaming error: {e}")
            raise RuntimeError(f"Zhipu streaming error: {e}")

    async def generate_with_functions(
        self,
        model: str,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        **kwargs,
    ) -> AdapterResponse:
        """
        使用工具/函数调用生成.

        Args:
            model: 模型名称
            messages: 消息列表
            tools: 工具定义列表
            **kwargs: 其他参数

        Returns:
            适配器响应 (可能包含tool_calls)
        """
        try:
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                **kwargs,
            }

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            choice = data["choices"][0]
            message = choice["message"]
            usage = data.get("usage", {})

            # 检查是否有工具调用
            function_call_data = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_call = message["tool_calls"][0]
                function_call_data = {
                    "name": tool_call["function"]["name"],
                    "arguments": tool_call["function"]["arguments"],
                }

            return AdapterResponse(
                provider=self.provider,
                model=data.get("model", model),
                content=message.get("content"),
                finish_reason=choice.get("finish_reason"),
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                function_call=function_call_data,
                metadata={"id": data.get("id")},
            )

        except httpx.HTTPError as e:
            logger.error(f"Zhipu function calling HTTP error: {e}")
            raise RuntimeError(f"Zhipu function calling HTTP error: {e}")
        except Exception as e:
            logger.error(f"Zhipu function calling error: {e}")
            raise RuntimeError(f"Zhipu function calling error: {e}")

    async def create_embedding(
        self,
        model: str,
        input_text: str | List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        创建文本嵌入.

        Args:
            model: 嵌入模型名称 (如 embedding-2)
            input_text: 输入文本或文本列表
            **kwargs: 其他参数

        Returns:
            嵌入结果
        """
        try:
            payload = {
                "model": model,
                "input": input_text,
                **kwargs,
            }

            response = await self.client.post(
                f"{self.base_url}/embeddings",
                json=payload,
            )
            response.raise_for_status()

            data = response.json()

            return {
                "provider": self.provider,
                "model": data.get("model", model),
                "embeddings": [item["embedding"] for item in data["data"]],
                "usage": data.get("usage", {}),
                "metadata": {"id": data.get("id")},
            }

        except httpx.HTTPError as e:
            logger.error(f"Zhipu embedding HTTP error: {e}")
            raise RuntimeError(f"Zhipu embedding HTTP error: {e}")
        except Exception as e:
            logger.error(f"Zhipu embedding error: {e}")
            raise RuntimeError(f"Zhipu embedding error: {e}")

    async def health_check(self) -> bool:
        """
        健康检查.

        Returns:
            是否健康
        """
        try:
            # 尝试发送一个最小请求
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "glm-4",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Zhipu health check failed: {e}")
            return False

    async def close(self):
        """关闭客户端."""
        await self.client.aclose()
