"""RAG API路由."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_config
from app.infrastructure.retrieval_client import RetrievalClient
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])

# 全局服务实例 (在main.py中初始化)
rag_service: RAGService | None = None


def init_rag_service() -> None:
    """初始化RAG服务."""
    global rag_service

    try:
        # 加载配置
        config = get_config()

        # 创建Retrieval客户端
        retrieval_client = RetrievalClient(
            base_url=config.retrieval_service_url,
            timeout=config.retrieval_timeout,
        )

        # 创建OpenAI客户端（通过model-adapter或直接连接）
        # 优先使用MODEL_ADAPTER_URL，实现统一LLM调用
        llm_client = AsyncOpenAI(
            api_key=config.llm_api_key or "dummy-key",
            base_url=config.llm_api_base,
            timeout=config.llm_timeout,
        )

        # 创建RAG服务
        rag_service = RAGService(
            retrieval_client=retrieval_client,
            llm_client=llm_client,
            model=config.llm_model,
        )

        logger.info(
            f"RAG service initialized - Model: {config.llm_model}, "
            f"Retrieval: {config.retrieval_service_url}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}", exc_info=True)
        raise RuntimeError(f"RAG service initialization failed: {e}") from e


# 批量请求最大限制
MAX_BATCH_SIZE = 50

# API模型
class RAGRequest(BaseModel):
    """RAG请求."""

    query: str = Field(..., description="用户查询", min_length=1, max_length=5000)
    tenant_id: str | None = Field(None, description="租户ID")
    rewrite_method: str = Field("multi", description="查询改写方法 (multi/hyde/none)")
    top_k: int = Field(10, description="检索结果数量", ge=1, le=50)
    stream: bool = Field(False, description="是否流式返回")
    include_citations: bool = Field(True, description="是否包含引用")


class RAGResponse(BaseModel):
    """RAG响应."""

    answer: str
    citations: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}


class BatchRAGRequest(BaseModel):
    """批量RAG请求."""

    queries: list[str] = Field(..., description="查询列表", min_length=1, max_length=50)
    tenant_id: str | None = Field(None, description="租户ID")
    rewrite_method: str = Field("none", description="查询改写方法")
    top_k: int = Field(10, description="检索结果数量", ge=1, le=50)


@router.post("/generate", response_model=RAGResponse)
async def generate(request: RAGRequest) -> RAGResponse:
    """
    生成答案 (非流式).

    基于检索到的知识生成答案，并附带引用来源。
    """
    if not rag_service:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized",
        )

    try:
        result = await rag_service.generate(
            query=request.query,
            tenant_id=request.tenant_id,
            rewrite_method=request.rewrite_method,
            top_k=request.top_k,
            stream=False,
            include_citations=request.include_citations,
        )

        return RAGResponse(**result)

    except ValueError as e:
        logger.warning(f"Invalid request parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}",
        ) from e
    except TimeoutError as e:
        logger.error(f"Request timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout - please try again",
        ) from e
    except Exception as e:
        logger.error(f"RAG generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        ) from e


@router.post("/generate/stream")
async def generate_stream(request: RAGRequest) -> StreamingResponse:
    """
    生成答案 (流式).

    流式返回生成的答案，使用Server-Sent Events (SSE)格式。
    """
    if not rag_service:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized",
        )

    async def event_stream():
        """SSE事件流."""
        try:
            async for event in rag_service.generate_stream(
                query=request.query,
                tenant_id=request.tenant_id,
                rewrite_method=request.rewrite_method,
                top_k=request.top_k,
            ):
                # 发送SSE格式数据
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            error_data = json.dumps({
                "type": "error",
                "message": str(e),
                "error_type": type(e).__name__,
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        finally:
            # 发送流结束标记
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        },
    )


@router.post("/batch", response_model=list[RAGResponse])
async def batch_generate(request: BatchRAGRequest) -> list[RAGResponse]:
    """
    批量生成答案.

    适用于需要同时处理多个查询的场景。
    """
    if not rag_service:
        logger.error("RAG service not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialized",
        )

    if len(request.queries) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_BATCH_SIZE} queries allowed per batch",
        )

    try:
        results = await rag_service.batch_generate(
            queries=request.queries,
            tenant_id=request.tenant_id,
            rewrite_method=request.rewrite_method,
            top_k=request.top_k,
        )

        responses = []
        for r in results:
            if "answer" in r:
                responses.append(RAGResponse(**r))
            else:
                # 处理失败的项
                responses.append(
                    RAGResponse(
                        answer="",
                        citations=[],
                        metadata={"error": r.get("error", "Unknown error")},
                    )
                )

        return responses

    except Exception as e:
        logger.error(f"Batch generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch generation failed: {str(e)}",
        ) from e


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    RAG服务健康检查.

    Returns:
        健康状态信息，包含依赖服务状态
    """
    if not rag_service:
        return {
            "status": "unhealthy",
            "reason": "Service not initialized",
            "details": {
                "retrieval_service": "unknown",
            },
        }

    try:
        # 检查Retrieval Service是否可用
        retrieval_ok = await rag_service.retrieval_client.health_check()

        overall_status = "healthy" if retrieval_ok else "degraded"

        return {
            "status": overall_status,
            "details": {
                "retrieval_service": "ok" if retrieval_ok else "unavailable",
                "llm_client": "ok",  # LLM客户端初始化成功
            },
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "reason": str(e),
            "details": {
                "retrieval_service": "error",
            },
        }
