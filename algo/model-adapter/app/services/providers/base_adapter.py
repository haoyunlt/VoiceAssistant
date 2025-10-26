"""基础适配器抽象类"""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import ChatResponse, CompletionResponse, EmbeddingResponse


class BaseAdapter(ABC):
    """基础适配器抽象类"""

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """聊天接口"""
        pass

    @abstractmethod
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """流式聊天接口"""
        pass

    @abstractmethod
    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """补全接口"""
        pass

    @abstractmethod
    async def completion_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """流式补全接口"""
        pass

    @abstractmethod
    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """向量化接口"""
        pass
