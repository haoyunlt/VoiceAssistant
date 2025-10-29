"""OpenAI适配器"""
import logging
import time
import uuid
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings
from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import (
    ChatChoice,
    ChatResponse,
    CompletionChoice,
    CompletionResponse,
    EmbeddingData,
    EmbeddingResponse,
    Usage,
)
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """OpenAI适配器"""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_base = settings.OPENAI_API_BASE
        self.timeout = settings.REQUEST_TIMEOUT

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": request.model,
                        "messages": [m.dict() for m in request.messages],
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                        "top_p": request.top_p,
                        "frequency_penalty": request.frequency_penalty,
                        "presence_penalty": request.presence_penalty,
                    },
                )

                response.raise_for_status()
                data = response.json()

                # 转换为统一格式
                return ChatResponse(
                    id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
                    model=data.get("model", request.model),
                    provider="openai",
                    choices=[
                        ChatChoice(
                            index=choice["index"],
                            message=choice["message"],
                            finish_reason=choice.get("finish_reason"),
                        )
                        for choice in data.get("choices", [])
                    ],
                    usage=Usage(**data.get("usage", {})),
                    created=data.get("created", int(time.time())),
                )

        except httpx.HTTPError as e:
            logger.error(f"OpenAI API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI adapter error: {e}")
            raise

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client, client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": request.model,
                    "messages": [m.dict() for m in request.messages],
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            raise

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口"""
        # OpenAI的completion API已废弃，转换为chat格式
        chat_request = ChatRequest(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )

        chat_response = await self.chat(chat_request)

        # 转换为completion格式
        return CompletionResponse(
            id=chat_response.id,
            model=chat_response.model,
            provider="openai",
            choices=[
                CompletionChoice(
                    index=choice.index,
                    text=choice.message.get("content", ""),
                    finish_reason=choice.finish_reason,
                )
                for choice in chat_response.choices
            ],
            usage=chat_response.usage,
            created=chat_response.created,
        )

    async def completion_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """流式补全接口"""
        chat_request = ChatRequest(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )

        async for chunk in self.chat_stream(chat_request):
            yield chunk

    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """向量化接口"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_base}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": request.model,
                        "input": request.input,
                    },
                )

                response.raise_for_status()
                data = response.json()

                return EmbeddingResponse(
                    model=data.get("model", request.model),
                    provider="openai",
                    data=[
                        EmbeddingData(
                            index=item["index"],
                            embedding=item["embedding"],
                        )
                        for item in data.get("data", [])
                    ],
                    usage=Usage(**data.get("usage", {})),
                )

        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise
