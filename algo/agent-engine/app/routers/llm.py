"""
LLM API - LLM 客户端 REST API

提供多厂商 LLM 的 REST API 接口
"""

from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger
from app.llm.base import Message
from app.llm.multi_llm_adapter import get_multi_llm_adapter

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/llm", tags=["LLM"])


class CompletionRequest(BaseModel):
    """LLM 完成请求"""

    messages: List[Message] = Field(..., description="消息列表")
    temperature: float = Field(0.7, description="温度参数 (0-2)", ge=0, le=2)
    max_tokens: int = Field(2000, description="最大 token 数", ge=1, le=32000)
    provider: Optional[Literal["openai", "claude", "ollama"]] = Field(
        None, description="指定 LLM 提供商（可选）"
    )
    stream: bool = Field(False, description="是否流式响应")


@router.post("/complete", summary="LLM 文本生成（多厂商 + 自动降级）")
async def complete(request: CompletionRequest):
    """
    使用多厂商 LLM 生成文本（支持自动降级）

    **降级策略**:
    - 首选: OpenAI GPT-4
    - 降级: Claude 3
    - 再降级: Ollama (本地)

    **特性**:
    - ✅ 自动降级保障可用性
    - ✅ 支持流式和非流式
    - ✅ 统一的消息格式
    - ✅ 工具调用支持（OpenAI/Claude）

    Args:
        messages: 消息列表
        temperature: 温度参数（控制随机性）
        max_tokens: 最大生成 token 数
        provider: 指定 LLM 提供商（可选）
        stream: 是否流式响应

    Returns:
        非流式: JSON 响应
        流式: SSE 流
    """
    try:
        adapter = get_multi_llm_adapter()

        if request.stream:
            # 流式响应
            stream, provider = await adapter.complete_stream(
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                provider_override=request.provider,
            )

            async def event_generator():
                try:
                    async for chunk in stream:
                        yield f"data: {chunk}\n\n"
                    yield f"data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "X-LLM-Provider": provider,
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        else:
            # 非流式响应
            response, provider = await adapter.complete(
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                provider_override=request.provider,
            )

            return {
                **response.dict(),
                "provider": provider,
            }

    except Exception as e:
        logger.error(f"LLM completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM completion failed: {str(e)}")


@router.get("/providers/status", summary="获取所有 LLM 提供商状态")
async def get_providers_status():
    """
    获取所有 LLM 提供商的健康状态

    Returns:
        提供商状态字典
    """
    try:
        adapter = get_multi_llm_adapter()
        status = adapter.get_status()
        return status

    except Exception as e:
        logger.error(f"Failed to get LLM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", summary="列出所有可用模型")
async def list_models():
    """
    列出所有可用的 LLM 模型

    Returns:
        模型列表
    """
    try:
        adapter = get_multi_llm_adapter()
        status = adapter.get_status()

        models = []

        # OpenAI 模型
        if status["providers"]["openai"]["healthy"]:
            models.extend(
                [
                    {
                        "provider": "openai",
                        "model": "gpt-4-turbo-preview",
                        "description": "GPT-4 Turbo (128K context)",
                        "context_length": 128000,
                        "pricing": "付费",
                    },
                    {
                        "provider": "openai",
                        "model": "gpt-3.5-turbo",
                        "description": "GPT-3.5 Turbo (16K context)",
                        "context_length": 16385,
                        "pricing": "付费",
                    },
                ]
            )

        # Claude 模型
        if status["providers"]["claude"]["healthy"]:
            models.extend(
                [
                    {
                        "provider": "claude",
                        "model": "claude-3-opus-20240229",
                        "description": "Claude 3 Opus (最强大)",
                        "context_length": 200000,
                        "pricing": "付费",
                    },
                    {
                        "provider": "claude",
                        "model": "claude-3-sonnet-20240229",
                        "description": "Claude 3 Sonnet (平衡)",
                        "context_length": 200000,
                        "pricing": "付费",
                    },
                    {
                        "provider": "claude",
                        "model": "claude-3-haiku-20240307",
                        "description": "Claude 3 Haiku (快速)",
                        "context_length": 200000,
                        "pricing": "付费",
                    },
                ]
            )

        # Ollama 模型
        if status["providers"]["ollama"]["healthy"]:
            ollama_models = status["providers"]["ollama"].get("available_models", [])
            models.extend(
                [
                    {
                        "provider": "ollama",
                        "model": model,
                        "description": f"本地模型 {model}",
                        "context_length": "取决于模型",
                        "pricing": "免费",
                    }
                    for model in ollama_models
                ]
            )

        return {
            "models": models,
            "count": len(models),
            "providers_available": [
                p for p, v in status["providers"].items() if v["healthy"]
            ],
        }

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))
