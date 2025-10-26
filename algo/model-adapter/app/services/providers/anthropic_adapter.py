"""Anthropic (Claude)适配器"""
import json
import logging
import time
import uuid
from typing import AsyncIterator

import httpx

from app.core.config import settings
from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import (
    ChatChoice,
    ChatResponse,
    CompletionChoice,
    CompletionResponse,
    EmbeddingResponse,
    Usage,
)
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseAdapter):
    """Anthropic适配器"""

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.api_base = settings.ANTHROPIC_API_BASE
        self.timeout = settings.REQUEST_TIMEOUT

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        try:
            # 转换消息格式（Anthropic格式略有不同）
            messages = []
            system_message = ""

            for msg in request.messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    messages.append({"role": msg.role, "content": msg.content})

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": request.model,
                    "messages": messages,
                    "max_tokens": request.max_tokens or 4096,
                    "temperature": request.temperature,
                }

                if system_message:
                    payload["system"] = system_message

                response = await client.post(
                    f"{self.api_base}/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                response.raise_for_status()
                data = response.json()

                # 转换为统一格式
                return ChatResponse(
                    id=data.get("id", f"msg-{uuid.uuid4().hex[:8]}"),
                    model=data.get("model", request.model),
                    provider="anthropic",
                    choices=[
                        ChatChoice(
                            index=0,
                            message={
                                "role": "assistant",
                                "content": data.get("content", [{}])[0].get("text", ""),
                            },
                            finish_reason=data.get("stop_reason"),
                        )
                    ],
                    usage=Usage(
                        prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
                        completion_tokens=data.get("usage", {}).get("output_tokens", 0),
                        total_tokens=data.get("usage", {}).get("input_tokens", 0)
                        + data.get("usage", {}).get("output_tokens", 0),
                    ),
                    created=int(time.time()),
                )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        # Anthropic支持流式，实现与OpenAI类似
        logger.info("Anthropic stream not fully implemented")
        yield "data: [DONE]\n\n"

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口"""
        # 转换为chat格式
        chat_request = ChatRequest(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        chat_response = await self.chat(chat_request)

        return CompletionResponse(
            id=chat_response.id,
            model=chat_response.model,
            provider="anthropic",
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
        yield "data: [DONE]\n\n"

    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """向量化接口"""
        # Anthropic不提供embedding服务
        raise NotImplementedError("Anthropic does not provide embedding service")
