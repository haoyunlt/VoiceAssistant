"""
Base Adapter - Abstract base class for all model adapters
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Chat message"""

    role: str  # system, user, assistant, tool
    content: str
    name: str = None
    tool_calls: list[dict] = None
    tool_call_id: str = None


@dataclass
class CompletionRequest:
    """Completion request"""

    messages: list[Message]
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    stream: bool = False
    tools: list[dict] = None
    tool_choice: str = "auto"


@dataclass
class CompletionResponse:
    """Completion response"""

    id: str
    content: str
    model: str
    role: str = "assistant"
    finish_reason: str = None
    tool_calls: list[dict] = None
    usage: dict[str, int] = None


@dataclass
class EmbeddingRequest:
    """Embedding request"""

    texts: list[str]
    model: str


@dataclass
class EmbeddingResponse:
    """Embedding response"""

    embeddings: list[list[float]]
    model: str
    usage: dict[str, int] = None


class BaseAdapter(ABC):
    """Abstract base adapter for LLM APIs"""

    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.extra_config = kwargs
        logger.info(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion"""
        pass

    @abstractmethod
    async def complete_stream(self, request: CompletionRequest) -> AsyncGenerator[str, None]:
        """Generate completion with streaming"""
        pass

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings"""
        pass

    @abstractmethod
    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get model information"""
        pass

    def count_tokens(self, text: str) -> int:
        """Count tokens (simple approximation)"""
        # In production, use tiktoken or model-specific tokenizer
        return len(text.split())

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD"""
        model_info = self.get_model_info(model)
        input_cost = input_tokens / 1000 * model_info.get("input_cost_per_1k", 0)
        output_cost = output_tokens / 1000 * model_info.get("output_cost_per_1k", 0)
        return input_cost + output_cost
