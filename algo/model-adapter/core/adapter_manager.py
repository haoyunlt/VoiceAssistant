"""
Adapter Manager - Manage all model adapters
"""

import logging
from typing import Any

from .base_adapter import (
    BaseAdapter,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)
from .claude_adapter import ClaudeAdapter
from .openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)


class AdapterManager:
    """Manage all model adapters"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.adapters: dict[str, BaseAdapter] = {}
        self._initialize_adapters()

    def _initialize_adapters(self):
        """Initialize all adapters from config"""

        # OpenAI
        if "openai" in self.config:
            openai_config = self.config["openai"]
            self.adapters["openai"] = OpenAIAdapter(
                api_key=openai_config.get("api_key"), base_url=openai_config.get("base_url")
            )
            logger.info("Initialized OpenAI adapter")

        # Claude
        if "anthropic" in self.config:
            claude_config = self.config["anthropic"]
            self.adapters["anthropic"] = ClaudeAdapter(api_key=claude_config.get("api_key"))
            logger.info("Initialized Claude adapter")

        # 通义千问 (Qwen) - Using OpenAI-compatible API
        if "qwen" in self.config:
            qwen_config = self.config["qwen"]
            self.adapters["qwen"] = OpenAIAdapter(
                api_key=qwen_config.get("api_key"),
                base_url=qwen_config.get(
                    "base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
                ),
            )
            logger.info("Initialized Qwen adapter")

        # Add more adapters here...

    def get_adapter(self, provider: str) -> BaseAdapter:
        """Get adapter by provider name"""
        if provider not in self.adapters:
            raise ValueError(f"Adapter not found for provider: {provider}")
        return self.adapters[provider]

    async def complete(self, provider: str, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using specified provider"""
        adapter = self.get_adapter(provider)
        return await adapter.complete(request)

    async def complete_stream(self, provider: str, request: CompletionRequest):
        """Generate completion with streaming"""
        adapter = self.get_adapter(provider)
        async for chunk in adapter.complete_stream(request):
            yield chunk

    async def embed(self, provider: str, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings using specified provider"""
        adapter = self.get_adapter(provider)
        return await adapter.embed(request)

    def get_model_info(self, provider: str, model: str) -> dict[str, Any]:
        """Get model information"""
        adapter = self.get_adapter(provider)
        return adapter.get_model_info(model)

    def list_providers(self) -> list:
        """List all available providers"""
        return list(self.adapters.keys())

    def is_provider_available(self, provider: str) -> bool:
        """Check if provider is available"""
        return provider in self.adapters
