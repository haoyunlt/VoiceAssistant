"""
OpenAI Adapter - Adapter for OpenAI API
"""

import logging
from typing import List, Dict, Any, AsyncGenerator
import openai
from openai import AsyncOpenAI

from .base_adapter import BaseAdapter, CompletionRequest, CompletionResponse, EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)


class OpenAIAdapter(BaseAdapter):
    """OpenAI API adapter"""
    
    # Model pricing (USD per 1K tokens)
    MODEL_PRICING = {
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-large": {"input": 0.00013, "output": 0},
        "text-embedding-3-small": {"input": 0.00002, "output": 0},
    }
    
    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1"
        )
    
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion"""
        try:
            # Convert messages
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            # Call API
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                stream=False,
                tools=request.tools,
                tool_choice=request.tool_choice if request.tools else None
            )
            
            choice = response.choices[0]
            message = choice.message
            
            return CompletionResponse(
                id=response.id,
                content=message.content or "",
                model=response.model,
                role=message.role,
                finish_reason=choice.finish_reason,
                tool_calls=[
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (message.tool_calls or [])
                ],
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        
        except Exception as e:
            logger.error(f"OpenAI completion error: {e}", exc_info=True)
            raise
    
    async def complete_stream(self, request: CompletionRequest) -> AsyncGenerator[str, None]:
        """Generate completion with streaming"""
        try:
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in request.messages
            ]
            
            stream = await self.client.chat.completions.create(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}", exc_info=True)
            raise
    
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate embeddings"""
        try:
            response = await self.client.embeddings.create(
                model=request.model,
                input=request.texts
            )
            
            embeddings = [item.embedding for item in response.data]
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}", exc_info=True)
            raise
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """Get model information"""
        pricing = self.MODEL_PRICING.get(model, {"input": 0, "output": 0})
        
        return {
            "model_id": model,
            "provider": "openai",
            "input_cost_per_1k": pricing["input"],
            "output_cost_per_1k": pricing["output"],
            "max_tokens": 128000 if "turbo" in model else 8192,
            "supports_tools": True,
            "supports_vision": "4o" in model or "vision" in model
        }

