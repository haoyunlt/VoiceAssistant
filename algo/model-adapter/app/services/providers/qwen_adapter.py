"""
Qwen (通义千问) Adapter
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.models.chat import ChatRequest, ChatResponse, Choice, Message, Usage

logger = logging.getLogger(__name__)


class QwenAdapter:
    """Qwen (通义千问) adapter"""

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.supported_models = [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-max-longcontext",
            "qwen-vl-plus",
            "qwen-vl-max"
        ]

    async def chat(
        self,
        request: ChatRequest,
        **kwargs
    ) -> ChatResponse:
        """Chat completion"""
        try:
            # Build request
            qwen_request = {
                "model": request.model,
                "input": {
                    "messages": [
                        {"role": msg.role, "content": msg.content}
                        for msg in request.messages
                    ]
                },
                "parameters": {
                    "temperature": request.temperature or 0.7,
                    "max_tokens": request.max_tokens or 2048,
                }
            }

            if request.top_p:
                qwen_request["parameters"]["top_p"] = request.top_p

            # Send request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await self.client.post(
                f"{self.base_url}/services/aigc/text-generation/generation",
                json=qwen_request,
                headers=headers
            )

            response.raise_for_status()
            result = response.json()

            # Convert to standard format
            return self._convert_response(result, request.model)

        except httpx.HTTPStatusError as e:
            logger.error(f"Qwen API HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Qwen chat completion failed: {e}")
            raise

    async def chat_stream(
        self,
        request: ChatRequest,
        **kwargs
    ) -> AsyncIterator[str]:
        """Streaming chat completion"""
        try:
            # Build request
            qwen_request = {
                "model": request.model,
                "input": {
                    "messages": [
                        {"role": msg.role, "content": msg.content}
                        for msg in request.messages
                    ]
                },
                "parameters": {
                    "temperature": request.temperature or 0.7,
                    "max_tokens": request.max_tokens or 2048,
                    "incremental_output": True
                }
            }

            if request.top_p:
                qwen_request["parameters"]["top_p"] = request.top_p

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "X-DashScope-SSE": "enable"
            }

            async with self.client.stream(
                "POST",
                f"{self.base_url}/services/aigc/text-generation/generation",
                json=qwen_request,
                headers=headers
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()

                        if not data or data == "[DONE]":
                            continue

                        try:
                            chunk = json.loads(data)
                            content = self._extract_stream_content(chunk)
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"Qwen streaming HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Qwen streaming failed: {e}")
            raise

    def _convert_response(self, result: dict, model: str) -> ChatResponse:
        """Convert Qwen response to standard format"""
        output = result.get("output", {})
        text = output.get("text", "")

        choices = [Choice(
            index=0,
            message=Message(
                role="assistant",
                content=text
            ),
            finish_reason=output.get("finish_reason", "stop")
        )]

        usage_data = result.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )

        return ChatResponse(
            id=result.get("request_id", ""),
            object="chat.completion",
            created=int(datetime.utcnow().timestamp()),
            model=model,
            choices=choices,
            usage=usage
        )

    def _extract_stream_content(self, chunk: dict) -> str | None:
        """Extract content from stream chunk"""
        try:
            output = chunk.get("output", {})
            return output.get("text", "")
        except Exception:
            pass
        return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def get_supported_models(self) -> list[str]:
        """Get list of supported models"""
        return self.supported_models
