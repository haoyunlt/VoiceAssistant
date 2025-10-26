"""百度文心适配器"""
import logging
from typing import AsyncIterator

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import ChatResponse, CompletionResponse, EmbeddingResponse
from app.services.providers.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class BaiduAdapter(BaseAdapter):
    """百度文心适配器"""

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口（示例实现）"""
        logger.info("Baidu chat adapter - placeholder implementation")
        raise NotImplementedError("Baidu adapter not fully implemented")

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        yield "data: [DONE]\n\n"

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口"""
        raise NotImplementedError("Baidu adapter not fully implemented")

    async def completion_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """流式补全接口"""
        yield "data: [DONE]\n\n"

    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """向量化接口"""
        raise NotImplementedError("Baidu adapter not fully implemented")
