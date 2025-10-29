"""
Claude Adapter - Adapter for Anthropic Claude API
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from anthropic import AsyncAnthropic

from .base_adapter import (
    BaseAdapter,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

logger = logging.getLogger(__name__)


class ClaudeAdapter(BaseAdapter):
    """Anthropic Claude API adapter"""

    # Model pricing (USD per 1M tokens)
    MODEL_PRICING = {
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
    }

    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion"""
        try:
            # Convert messages (Claude format)
            system_messages = [msg for msg in request.messages if msg.role == "system"]
            user_messages = [msg for msg in request.messages if msg.role != "system"]

            system = system_messages[0].content if system_messages else None

            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in user_messages
            ]

            # Call API
            response = await self.client.messages.create(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                system=system,
                messages=messages
            )

            content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": str(block.input)
                        }
                    })

            return CompletionResponse(
                id=response.id,
                content=content,
                model=response.model,
                role=response.role,
                finish_reason=response.stop_reason,
                tool_calls=tool_calls if tool_calls else None,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            )

        except Exception as e:
            logger.error(f"Claude completion error: {e}", exc_info=True)
            raise

    async def complete_stream(self, request: CompletionRequest) -> AsyncGenerator[str, None]:
        """Generate completion with streaming"""
        try:
            system_messages = [msg for msg in request.messages if msg.role == "system"]
            user_messages = [msg for msg in request.messages if msg.role != "system"]

            system = system_messages[0].content if system_messages else None

            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in user_messages
            ]

            async with self.client.messages.stream(
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                system=system,
                messages=messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Claude streaming error: {e}", exc_info=True)
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings - Claude doesn't support embeddings"""
        raise NotImplementedError("Claude does not support embeddings")

    def get_model_info(self, model: str) -> dict[str, Any]:
        """Get model information"""
        # Convert to per 1K tokens
        pricing = self.MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})

        return {
            "model_id": model,
            "provider": "anthropic",
            "input_cost_per_1k": pricing["input"] / 1000,
            "output_cost_per_1k": pricing["output"] / 1000,
            "max_tokens": 200000 if "claude-3" in model else 100000,
            "supports_tools": True,
            "supports_vision": "claude-3" in model
        }

