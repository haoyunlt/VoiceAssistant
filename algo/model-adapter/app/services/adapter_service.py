"""适配器服务 - 统一调度各个模型提供商"""

import logging
from collections.abc import AsyncIterator

from app.models.request import ChatRequest, CompletionRequest, EmbeddingRequest
from app.models.response import (
    ChatResponse,
    CompletionResponse,
    EmbeddingResponse,
)
from app.services.providers.anthropic_adapter import AnthropicAdapter
from app.services.providers.baidu_adapter import BaiduAdapter
from app.services.providers.openai_adapter import OpenAIAdapter
from app.services.providers.qwen_adapter import QwenAdapter
from app.services.providers.zhipu_adapter import ZhipuAdapter

logger = logging.getLogger(__name__)


class AdapterService:
    """适配器服务"""

    def __init__(self):
        # 初始化各个提供商的适配器
        self.openai_adapter = OpenAIAdapter()
        self.anthropic_adapter = AnthropicAdapter()
        self.zhipu_adapter = ZhipuAdapter()
        self.qwen_adapter = QwenAdapter()
        self.baidu_adapter = BaiduAdapter()

        # 提供商映射
        self.adapters = {
            "openai": self.openai_adapter,
            "azure-openai": self.openai_adapter,  # Azure使用OpenAI适配器
            "anthropic": self.anthropic_adapter,
            "zhipu": self.zhipu_adapter,
            "qwen": self.qwen_adapter,
            "baidu": self.baidu_adapter,
        }

    def _get_provider(self, model: str, provider: str = None) -> tuple:
        """
        根据模型名称或指定的提供商获取适配器

        Args:
            model: 模型名称
            provider: 指定的提供商

        Returns:
            (provider_name, adapter)
        """
        # 如果明确指定了提供商
        if provider and provider in self.adapters:
            return provider, self.adapters[provider]

        # 根据模型名称自动判断提供商
        if model.startswith("gpt-"):
            return "openai", self.openai_adapter
        elif model.startswith("claude-"):
            return "anthropic", self.anthropic_adapter
        elif model.startswith("glm-"):
            return "zhipu", self.zhipu_adapter
        elif model.startswith("qwen-"):
            return "qwen", self.qwen_adapter
        elif model.startswith("ERNIE-") or model.startswith("ernie-"):
            return "baidu", self.baidu_adapter

        # 默认使用OpenAI
        logger.warning(f"Unknown model: {model}, using OpenAI adapter")
        return "openai", self.openai_adapter

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        聊天接口

        Args:
            request: 聊天请求

        Returns:
            聊天响应
        """
        provider_name, adapter = self._get_provider(request.model, request.provider)

        logger.info(f"Routing to {provider_name} for model {request.model}")

        try:
            response = await adapter.chat(request)
            response.provider = provider_name
            return response

        except Exception as e:
            logger.error(f"Chat failed with {provider_name}: {e}", exc_info=True)
            raise

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        流式聊天接口

        Args:
            request: 聊天请求

        Yields:
            SSE格式的流式数据
        """
        provider_name, adapter = self._get_provider(request.model, request.provider)

        logger.info(f"Streaming from {provider_name} for model {request.model}")

        try:
            async for chunk in adapter.chat_stream(request):
                yield chunk

        except Exception as e:
            logger.error(f"Stream chat failed with {provider_name}: {e}", exc_info=True)
            raise

    async def completion(self, request: CompletionRequest) -> CompletionResponse:
        """
        补全接口

        Args:
            request: 补全请求

        Returns:
            补全响应
        """
        provider_name, adapter = self._get_provider(request.model, request.provider)

        logger.info(f"Routing to {provider_name} for completion")

        try:
            response = await adapter.completion(request)
            response.provider = provider_name
            return response

        except Exception as e:
            logger.error(f"Completion failed with {provider_name}: {e}", exc_info=True)
            raise

    async def completion_stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """
        流式补全接口

        Args:
            request: 补全请求

        Yields:
            SSE格式的流式数据
        """
        provider_name, adapter = self._get_provider(request.model, request.provider)

        logger.info(f"Streaming completion from {provider_name}")

        try:
            async for chunk in adapter.completion_stream(request):
                yield chunk

        except Exception as e:
            logger.error(f"Stream completion failed with {provider_name}: {e}", exc_info=True)
            raise

    async def embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        向量化接口

        Args:
            request: 向量化请求

        Returns:
            向量化响应
        """
        provider_name, adapter = self._get_provider(request.model, request.provider)

        logger.info(f"Routing to {provider_name} for embedding")

        try:
            response = await adapter.embedding(request)
            response.provider = provider_name
            return response

        except Exception as e:
            logger.error(f"Embedding failed with {provider_name}: {e}", exc_info=True)
            raise
