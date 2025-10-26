"""RAG API路由."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from ..infrastructure.retrieval_client import RetrievalClient
from ..services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])

# 全局服务实例 (在main.py中初始化)
rag_service: Optional[RAGService] = None


def init_rag_service():
    """初始化RAG服务."""
    global rag_service

    # 创建Retrieval客户端
    retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval-service:8012")
    retrieval_client = RetrievalClient(base_url=retrieval_url)

    # 创建OpenAI客户端
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, using mock mode")
        # 在生产环境应该抛出错误
        # raise ValueError("OPENAI_API_KEY is required")

    llm_client = AsyncOpenAI(api_key=api_key) if api_key else None

    # 创建RAG服务
    model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    rag_service = RAGService(
        retrieval_client=retrieval_client,
        llm_client=llm_client,
        model=model,
    )

    logger.info(f"RAG service initialized with model: {model}")


# API模型
class RAGRequest(BaseModel):
    """RAG请求."""

    query: str = Field(..., description="用户查询")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    rewrite_method: str = Field("multi", description="查询改写方法 (multi/hyde/none)")
    top_k: int = Field(10, description="检索结果数量", ge=1, le=50)
    stream: bool = Field(False, description="是否流式返回")
    include_citations: bool = Field(True, description="是否包含引用")


class RAGResponse(BaseModel):
    """RAG响应."""

    answer: str
    citations: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class BatchRAGRequest(BaseModel):
    """批量RAG请求."""

    queries: List[str] = Field(..., description="查询列表")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    rewrite_method: str = Field("none", description="查询改写方法")
    top_k: int = Field(10, description="检索结果数量")


@router.post("/generate", response_model=RAGResponse)
async def generate(request: RAGRequest):
    """
    生成答案 (非流式).

    基于检索到的知识生成答案，并附带引用来源。
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

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

    except Exception as e:
        logger.error(f"RAG generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/generate/stream")
async def generate_stream(request: RAGRequest):
    """
    生成答案 (流式).

    流式返回生成的答案，使用Server-Sent Events (SSE)格式。
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

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
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/batch", response_model=List[RAGResponse])
async def batch_generate(request: BatchRAGRequest):
    """
    批量生成答案.

    适用于需要同时处理多个查询的场景。
    """
    if not rag_service:
        raise HTTPException(status_code=503, detail="RAG service not initialized")

    try:
        results = await rag_service.batch_generate(
            queries=request.queries,
            tenant_id=request.tenant_id,
            rewrite_method=request.rewrite_method,
            top_k=request.top_k,
        )

        return [RAGResponse(**r) if "answer" in r else RAGResponse(answer="", metadata={"error": r.get("error")}) for r in results]

    except Exception as e:
        logger.error(f"Batch generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查."""
    if not rag_service:
        return {"status": "unhealthy", "reason": "Service not initialized"}

    try:
        # 检查Retrieval Service是否可用
        retrieval_ok = await rag_service.retrieval_client.health_check()

        return {
            "status": "healthy" if retrieval_ok else "degraded",
            "retrieval_service": "ok" if retrieval_ok else "unavailable",
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "reason": str(e)}
