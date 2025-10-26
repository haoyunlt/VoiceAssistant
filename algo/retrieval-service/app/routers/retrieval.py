"""
Retrieval API endpoints
"""

from fastapi import APIRouter, HTTPException

from app.core.logging_config import get_logger
from app.models.retrieval import (
    BM25Request,
    BM25Response,
    HybridRequest,
    HybridResponse,
    VectorRequest,
    VectorResponse,
)
from app.services.retrieval_service import RetrievalService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval"])

# 全局服务实例
retrieval_service = RetrievalService()


@router.post("/vector", response_model=VectorResponse)
async def vector_search(request: VectorRequest):
    """
    向量检索

    - **query**: 查询文本
    - **query_embedding**: 查询向量（可选）
    - **top_k**: 返回的文档数量
    - **tenant_id**: 租户ID
    - **filters**: 过滤条件
    """
    try:
        logger.info(f"Vector search request: query={request.query[:50]}, top_k={request.top_k}")
        response = await retrieval_service.vector_search(request)
        logger.info(f"Vector search completed: found {len(response.documents)} documents")
        return response
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")


@router.post("/bm25", response_model=BM25Response)
async def bm25_search(request: BM25Request):
    """
    BM25 检索

    - **query**: 查询文本
    - **top_k**: 返回的文档数量
    - **tenant_id**: 租户ID
    - **filters**: 过滤条件
    """
    try:
        logger.info(f"BM25 search request: query={request.query[:50]}, top_k={request.top_k}")
        response = await retrieval_service.bm25_search(request)
        logger.info(f"BM25 search completed: found {len(response.documents)} documents")
        return response
    except Exception as e:
        logger.error(f"BM25 search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"BM25 search failed: {str(e)}")


@router.post("/hybrid", response_model=HybridResponse)
async def hybrid_search(request: HybridRequest):
    """
    混合检索（向量 + BM25 + RRF融合 + 重排序）

    - **query**: 查询文本
    - **query_embedding**: 查询向量（可选）
    - **top_k**: 最终返回的文档数量
    - **tenant_id**: 租户ID
    - **filters**: 过滤条件
    - **enable_rerank**: 是否启用重排序
    - **rerank_top_k**: 重排序后返回的文档数量
    """
    try:
        logger.info(
            f"Hybrid search request: query={request.query[:50]}, "
            f"top_k={request.top_k}, enable_rerank={request.enable_rerank}"
        )
        response = await retrieval_service.hybrid_search(request)
        logger.info(
            f"Hybrid search completed: found {len(response.documents)} documents, "
            f"reranked={response.reranked}"
        )
        return response
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")
