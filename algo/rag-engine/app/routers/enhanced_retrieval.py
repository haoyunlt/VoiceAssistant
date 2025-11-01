"""
Enhanced Retrieval API - 增强检索 API

提供 Re-ranking 和 Hybrid Search 功能
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.reranking.reranker import get_reranker
from app.retrieval.hybrid_retriever import get_hybrid_retriever

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/retrieval", tags=["Enhanced Retrieval"])


class Document(BaseModel):
    """文档模型"""

    id: str | None = None
    text: str
    score: float | None = None


class ReRankRequest(BaseModel):
    """Re-ranking 请求"""

    query: str = Field(..., description="查询文本")
    documents: list[Document] = Field(..., description="待重排序的文档列表")
    top_k: int = Field(10, description="返回的 top-k 结果", ge=1, le=100)
    use_fusion: bool = Field(False, description="是否使用分数融合")


class HybridSearchRequest(BaseModel):
    """混合检索请求"""

    query: str = Field(..., description="查询文本")
    vector_results: list[Document] = Field(..., description="向量检索结果")
    top_k: int = Field(10, description="返回的 top-k 结果", ge=1, le=100)
    fusion_method: Literal["rrf", "weighted_sum"] = Field("rrf", description="融合方法")


@router.post("/rerank", summary="Re-ranking（重排序）")
async def rerank_documents(request: ReRankRequest):
    """
    使用交叉编码器对检索结果进行重排序

    **特性**:
    - ✅ 基于 Cross-Encoder 的重排序
    - ✅ 提升检索精度
    - ✅ 支持分数融合
    - ✅ 自动降级（模型不可用时返回原始结果）

    **适用场景**:
    - 向量检索后的精排
    - 提升相关性
    - 多阶段检索

    Args:
        query: 查询文本
        documents: 待重排序的文档列表
        top_k: 返回的 top-k 结果
        use_fusion: 是否使用分数融合

    Returns:
        重排序后的文档列表
    """
    try:
        reranker = get_reranker()

        # 转换为字典格式
        docs = [doc.dict() for doc in request.documents]

        # 重排序
        if request.use_fusion:
            reranked_docs = reranker.rerank_with_fusion(
                query=request.query,
                documents=docs,
            )
        else:
            reranked_docs = reranker.rerank(
                query=request.query,
                documents=docs,
            )

        logger.info(f"Re-ranked {len(docs)} documents, returning {len(reranked_docs)}")

        return {
            "query": request.query,
            "documents": reranked_docs[: request.top_k],
            "count": len(reranked_docs[: request.top_k]),
            "fusion_used": request.use_fusion,
        }

    except Exception as e:
        logger.error(f"Re-ranking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Re-ranking failed: {str(e)}") from e


@router.post("/hybrid-search", summary="混合检索（BM25 + Vector）")
async def hybrid_search(request: HybridSearchRequest):
    """
    混合检索：结合 BM25 和向量检索

    **特性**:
    - ✅ BM25 关键词检索
    - ✅ 向量语义检索
    - ✅ Reciprocal Rank Fusion (RRF)
    - ✅ 加权求和融合

    **适用场景**:
    - 提升召回率
    - 关键词 + 语义混合
    - 多路检索融合

    Args:
        query: 查询文本
        vector_results: 向量检索结果
        top_k: 返回的 top-k 结果
        fusion_method: 融合方法（rrf 或 weighted_sum）

    Returns:
        混合检索结果
    """
    try:
        hybrid_retriever = get_hybrid_retriever()

        # 转换为字典格式
        vector_results = [doc.dict() for doc in request.vector_results]

        # 混合检索
        hybrid_results = hybrid_retriever.retrieve(
            query=request.query,
            vector_results=vector_results,
            top_k=request.top_k,
            fusion_method=request.fusion_method,
        )

        logger.info(
            f"Hybrid search completed: {len(hybrid_results)} results, fusion={request.fusion_method}"
        )

        return {
            "query": request.query,
            "documents": hybrid_results,
            "count": len(hybrid_results),
            "fusion_method": request.fusion_method,
        }

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}") from e


@router.get("/status", summary="获取增强检索功能状态")
async def get_retrieval_status():
    """
    获取 Re-ranking 和 Hybrid Search 的状态

    Returns:
        状态信息
    """
    try:
        reranker = get_reranker()
        hybrid_retriever = get_hybrid_retriever()

        reranker_health = reranker.health_check()
        hybrid_health = hybrid_retriever.health_check()

        return {
            "reranking": reranker_health,
            "hybrid_search": hybrid_health,
        }

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
