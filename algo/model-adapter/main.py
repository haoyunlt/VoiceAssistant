"""Model Adapter服务 - 重构版本."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from app.core.adapter_manager import AdapterManager
from app.core.exceptions import (
    ModelAdapterError,
    ProviderNotAvailableError,
    ProviderNotFoundError,
)
from app.core.settings import settings
from app.models.request import ChatRequest, EmbeddingRequest
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import make_asgi_app

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format,
)
logger = logging.getLogger(__name__)

# 全局适配器管理器
adapter_manager: AdapterManager = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理."""
    global adapter_manager

    logger.info(f"Starting {settings.app_name} v{settings.app_version}...")
    logger.info(f"Environment: {settings.environment}")

    # 初始化适配器管理器
    adapter_manager = AdapterManager(settings)
    await adapter_manager.initialize()

    logger.info(f"{settings.app_name} started with {adapter_manager.adapter_count} providers")

    yield

    # 清理资源
    logger.info(f"Shutting down {settings.app_name}...")
    if adapter_manager:
        await adapter_manager.shutdown()
    logger.info(f"{settings.app_name} shut down complete")


# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    description="统一的LLM提供商适配层",
    version=settings.app_version,
    lifespan=lifespan,
    debug=settings.debug,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Prometheus指标
if settings.enable_metrics:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


# 依赖注入：获取适配器管理器
def get_adapter_manager() -> AdapterManager:
    """获取适配器管理器."""
    if adapter_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized",
        )
    return adapter_manager


# 全局异常处理器
@app.exception_handler(ModelAdapterError)
async def model_adapter_error_handler(_request: Request, exc: ModelAdapterError):
    """处理模型适配器异常."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    # 根据异常类型设置状态码
    if isinstance(exc, ProviderNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ProviderNotAvailableError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    logger.error(f"ModelAdapterError: {exc.message}", extra=exc.to_dict())

    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(_request: Request, exc: Exception):
    """处理通用异常."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.debug else None,
        },
    )


# ===== API Endpoints =====


@app.get("/health")
async def health_check(manager: Annotated[AdapterManager, Depends(get_adapter_manager)]):
    """健康检查."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "providers": manager.list_providers(),
        "provider_count": manager.adapter_count,
    }


@app.get("/api/v1/providers")
async def list_providers(manager: Annotated[AdapterManager, Depends(get_adapter_manager)]):
    """列出可用的提供商及其健康状态."""
    provider_status = await manager.get_all_provider_status()

    return {
        "providers": provider_status,
        "count": len(provider_status),
    }


@app.post("/api/v1/generate")
async def generate(
    request: ChatRequest,
    manager: Annotated[AdapterManager, Depends(get_adapter_manager)],
):
    """
    生成文本 (非流式).

    Args:
        request: 聊天请求
        manager: 适配器管理器

    Returns:
        生成结果
    """
    # 获取适配器
    provider = request.provider or "openai"  # 默认使用openai
    adapter = manager.get_adapter(provider)

    try:
        # 转换消息格式
        messages = [msg.dict() for msg in request.messages]

        response = await adapter.generate(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
        )

        return {
            "provider": response.provider,
            "model": response.model,
            "content": response.content,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
            "metadata": response.metadata,
        }

    except Exception as e:
        logger.error(f"Generation failed for {provider}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        ) from e


@app.post("/api/v1/generate/stream")
async def generate_stream(
    request: ChatRequest,
    manager: Annotated[AdapterManager, Depends(get_adapter_manager)],
):
    """
    生成文本 (流式).

    使用Server-Sent Events (SSE)格式返回。

    Args:
        request: 聊天请求
        manager: 适配器管理器

    Returns:
        SSE流
    """
    # 获取适配器
    provider = request.provider or "openai"
    adapter = manager.get_adapter(provider)

    async def event_stream():
        """SSE事件流."""
        try:
            # 转换消息格式
            messages = [msg.dict() for msg in request.messages]

            async for chunk in adapter.generate_stream(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                import json

                data = json.dumps(
                    {
                        "provider": chunk.provider,
                        "model": chunk.model,
                        "content": chunk.content,
                        "finish_reason": chunk.finish_reason,
                    },
                    ensure_ascii=False,
                )
                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed for {provider}: {e}", exc_info=True)
            import json

            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        },
    )


@app.post("/api/v1/embeddings")
async def create_embeddings(
    request: EmbeddingRequest,
    manager: Annotated[AdapterManager, Depends(get_adapter_manager)],
):
    """
    创建文本嵌入.

    Args:
        request: 嵌入请求
        manager: 适配器管理器

    Returns:
        嵌入结果
    """
    # 获取适配器
    provider = request.provider or "openai"
    adapter = manager.get_adapter(provider)

    # 检查是否支持嵌入
    if not hasattr(adapter, "create_embedding"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' does not support embeddings",
        )

    try:
        result = await adapter.create_embedding(
            model=request.model,
            input_text=request.input,
        )

        return result

    except Exception as e:
        logger.error(f"Embedding failed for {provider}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding failed: {str(e)}",
        ) from e


from typing import Any  # noqa: E402

from pydantic import BaseModel  # noqa: E402


class ProtocolConvertRequest(BaseModel):
    """协议转换请求模型"""

    target_provider: str
    messages: list[dict[str, Any]]
    parameters: dict[str, Any] = {}


class CostCalculateRequest(BaseModel):
    """成本计算请求模型"""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@app.post("/api/v1/convert")
async def convert_protocol(request: ProtocolConvertRequest):
    """
    协议转换.

    将统一格式转换为特定Provider格式。
    """
    from app.core.protocol_converter import ProtocolConverter

    if request.target_provider == "openai":
        result = ProtocolConverter.to_openai_format(request.messages, request.parameters)
    elif request.target_provider == "claude":
        result = ProtocolConverter.to_claude_format(request.messages, request.parameters)
    elif request.target_provider == "zhipu":
        result = ProtocolConverter.to_zhipu_format(request.messages, request.parameters)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {request.target_provider}",
        )

    return result


@app.post("/api/v1/cost/calculate")
async def calculate_cost(request: CostCalculateRequest):
    """
    计算成本.

    Args:
        request: 包含model, input_tokens, output_tokens的请求

    Returns:
        成本详情
    """
    from app.core.cost_calculator import CostCalculator

    cost = CostCalculator.calculate_cost(request.model, request.input_tokens, request.output_tokens)

    return cost


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {settings.host}:{settings.port}")

    uvicorn.run(
        "main_refactored:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
