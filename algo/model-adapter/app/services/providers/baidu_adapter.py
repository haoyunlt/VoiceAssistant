"""
Baidu ERNIE (文心一言) Adapter
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx

from app.models.chat import ChatRequest, ChatResponse, Choice, Message, Usage

logger = logging.getLogger(__name__)


class BaiduAdapter:
    """Baidu ERNIE (文心一言) adapter"""

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.client = httpx.AsyncClient(timeout=60.0)
        self.access_token = None
        self.token_expires_at = None
        self.supported_models = [
            "ernie-bot",
            "ernie-bot-turbo",
            "ernie-bot-4",
            "ernie-bot-8k",
            "bloomz-7b",
            "ernie-speed",
        ]

    async def _get_access_token(self) -> str:
        """Get access token"""
        # Check if token is still valid
        if self.access_token and self.token_expires_at:  # noqa: SIM102
            if datetime.utcnow() < self.token_expires_at:
                return self.access_token

        # Request new token
        try:
            url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            }

            response = await self.client.post(url, params=params)
            response.raise_for_status()
            result = response.json()

            self.access_token = result["access_token"]
            expires_in = result.get("expires_in", 86400)  # Default 24 hours
            self.token_expires_at = datetime.utcnow() + timedelta(
                seconds=expires_in - 300
            )  # 5 min buffer

            logger.info("Baidu access token obtained successfully")
            return self.access_token

        except Exception as e:
            logger.error(f"Failed to get Baidu access token: {e}")
            raise

    async def chat(self, request: ChatRequest, **_kwargs) -> ChatResponse:
        """Chat completion"""
        try:
            # Get access token
            access_token = await self._get_access_token()

            # Map model to endpoint
            endpoint = self._get_model_endpoint(request.model)

            # Build request
            baidu_request = {
                "messages": [
                    {"role": msg.role, "content": msg.content} for msg in request.messages
                ],
                "temperature": request.temperature or 0.95,
                "top_p": request.top_p or 0.8,
            }

            if request.max_tokens:
                baidu_request["max_output_tokens"] = request.max_tokens

            # Send request
            url = f"{endpoint}?access_token={access_token}"
            response = await self.client.post(url, json=baidu_request)

            response.raise_for_status()
            result = response.json()

            # Check for API errors
            if "error_code" in result:
                raise Exception(f"Baidu API error: {result.get('error_msg', 'Unknown error')}")

            # Convert to standard format
            return self._convert_response(result, request.model)

        except httpx.HTTPStatusError as e:
            logger.error(f"Baidu API HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Baidu chat completion failed: {e}")
            raise

    async def chat_stream(self, request: ChatRequest, **_kwargs) -> AsyncIterator[str]:
        """Streaming chat completion"""
        try:
            # Get access token
            access_token = await self._get_access_token()

            # Map model to endpoint
            endpoint = self._get_model_endpoint(request.model)

            # Build request
            baidu_request = {
                "messages": [
                    {"role": msg.role, "content": msg.content} for msg in request.messages
                ],
                "temperature": request.temperature or 0.95,
                "top_p": request.top_p or 0.8,
                "stream": True,
            }

            if request.max_tokens:
                baidu_request["max_output_tokens"] = request.max_tokens

            # Send streaming request
            url = f"{endpoint}?access_token={access_token}"

            async with self.client.stream("POST", url, json=baidu_request) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]

                        if not data:
                            continue

                        try:
                            chunk = json.loads(data)
                            content = self._extract_stream_content(chunk)
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"Baidu streaming HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Baidu streaming failed: {e}")
            raise

    def _get_model_endpoint(self, model: str) -> str:
        """Get API endpoint for model"""
        endpoint_map = {
            "ernie-bot": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions",
            "ernie-bot-turbo": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant",
            "ernie-bot-4": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
            "ernie-bot-8k": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie_bot_8k",
            "bloomz-7b": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/bloomz_7b1",
            "ernie-speed": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie_speed",
        }

        return endpoint_map.get(
            model, "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"
        )

    def _convert_response(self, result: dict, model: str) -> ChatResponse:
        """Convert Baidu response to standard format"""
        text = result.get("result", "")

        choices = [
            Choice(
                index=0,
                message=Message(role="assistant", content=text),
                finish_reason=result.get("finish_reason", "stop")
                if result.get("is_end")
                else "length",
            )
        ]

        usage_data = result.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return ChatResponse(
            id=result.get("id", ""),
            object="chat.completion",
            created=result.get("created", int(datetime.utcnow().timestamp())),
            model=model,
            choices=choices,
            usage=usage,
        )

    def _extract_stream_content(self, chunk: dict) -> str | None:
        """Extract content from stream chunk"""
        try:
            return chunk.get("result", "")
        except Exception:
            pass
        return None

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    def get_supported_models(self) -> list[str]:
        """Get list of supported models"""
        return self.supported_models
