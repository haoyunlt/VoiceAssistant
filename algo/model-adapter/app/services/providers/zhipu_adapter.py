"""
Zhipu AI (GLM) Adapter
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.models.chat import ChatRequest, ChatResponse, Choice, Message, Usage

logger = logging.getLogger(__name__)


class ZhipuAdapter:
    """Zhipu AI (智谱AI) adapter for GLM series models"""

    def __init__(self, api_key: str, base_url: str = "https://open.bigmodel.cn/api/paas/v4"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.supported_models = [
            "glm-4",
            "glm-4v",
            "glm-3-turbo",
            "chatglm_turbo",
            "chatglm_pro",
            "chatglm_std",
            "chatglm_lite"
        ]

    async def chat(
        self,
        request: ChatRequest,
        **kwargs
    ) -> ChatResponse:
        """Chat completion"""
        try:
            # Build request
            zhipu_request = {
                "model": request.model,
                "messages": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ],
                "temperature": request.temperature or 0.7,
                "max_tokens": request.max_tokens or 2048,
                "stream": False
            }

            # Add optional parameters
            if request.top_p:
                zhipu_request["top_p"] = request.top_p

            # Send request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=zhipu_request,
                headers=headers
            )

            response.raise_for_status()
            result = response.json()

            # Convert to standard format
            return self._convert_response(result)

        except httpx.HTTPStatusError as e:
            logger.error(f"Zhipu API HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Zhipu chat completion failed: {e}")
            raise

    async def chat_stream(
        self,
        request: ChatRequest,
        **kwargs
    ) -> AsyncIterator[str]:
        """Streaming chat completion"""
        try:
            # Build request
            zhipu_request = {
                "model": request.model,
                "messages": [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.messages
                ],
                "temperature": request.temperature or 0.7,
                "max_tokens": request.max_tokens or 2048,
                "stream": True
            }

            if request.top_p:
                zhipu_request["top_p"] = request.top_p

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }

            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=zhipu_request,
                headers=headers
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            content = self._extract_stream_content(chunk)
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"Zhipu streaming HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Zhipu streaming failed: {e}")
            raise

    def _convert_response(self, result: dict) -> ChatResponse:
        """Convert Zhipu response to standard format"""
        choices = []
        for choice in result.get("choices", []):
            message = choice.get("message", {})
            choices.append(Choice(
                index=choice.get("index", 0),
                message=Message(
                    role=message.get("role", "assistant"),
                    content=message.get("content", "")
                ),
                finish_reason=choice.get("finish_reason", "stop")
            ))

        usage_data = result.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )

        return ChatResponse(
            id=result.get("id", ""),
            object="chat.completion",
            created=result.get("created", int(datetime.utcnow().timestamp())),
            model=result.get("model", ""),
            choices=choices,
            usage=usage
        )

    def _extract_stream_content(self, chunk: dict) -> str | None:
        """Extract content from stream chunk"""
        try:
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                return delta.get("content", "")
        except Exception:
            pass
        return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def get_supported_models(self) -> list[str]:
        """Get list of supported models"""
        return self.supported_models
