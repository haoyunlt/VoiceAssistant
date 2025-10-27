"""
Main retrieval orchestration service
"""

import asyncio
import time
from typing import List

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.retrieval import (
    BM25Request,
    BM25Response,
    HybridRequest,
    HybridResponse,
    RetrievalDocument,
    VectorRequest,
    VectorResponse,
)
from app.services.bm25_service import BM25Service
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_service import HybridService
from app.services.rerank_service import RerankService
from app.services.vector_service import VectorService

logger = get_logger(__name__)


class RetrievalService:
    """检索编排服务"""

    def __init__(self):
        self.vector_service = VectorService()
        self.bm25_service = BM25Service()
        self.hybrid_service = HybridService(rrf_k=settings.RRF_K)
        self.rerank_service = RerankService()
        self.embedding_service = EmbeddingService()

    async def vector_search(self, request: VectorRequest) -> VectorResponse:
        """向量检索"""
        start_time = time.time()

        # 如果没有提供向量，自动获取向量
        query_embedding = request.query_embedding
        if not query_embedding:
            if not request.query:
                logger.warning("No query or embedding provided")
                return VectorResponse(
                    documents=[], query=request.query or "", latency_ms=(time.time() - start_time) * 1000
                )

            # 使用embedding服务获取向量
            logger.info(f"Generating embedding for query: {request.query[:50]}...")
            query_embedding = await self.embedding_service.embed_query(request.query)

        # 执行向量检索
        top_k = request.top_k or settings.VECTOR_TOP_K
        documents = await self.vector_service.search(
            query_embedding=query_embedding,
            top_k=top_k,
            tenant_id=request.tenant_id,
            filters=request.filters,
        )

        latency_ms = (time.time() - start_time) * 1000

        return VectorResponse(documents=documents, query=request.query, latency_ms=latency_ms)

    async def bm25_search(self, request: BM25Request) -> BM25Response:
        """BM25 检索"""
        start_time = time.time()

        # 执行 BM25 检索
        top_k = request.top_k or settings.BM25_TOP_K
        documents = await self.bm25_service.search(
            query=request.query,
            top_k=top_k,
            tenant_id=request.tenant_id,
            filters=request.filters,
        )

        latency_ms = (time.time() - start_time) * 1000

        return BM25Response(documents=documents, query=request.query, latency_ms=latency_ms)

    async def hybrid_search(self, request: HybridRequest) -> HybridResponse:
        """混合检索（向量 + BM25 + RRF融合 + 重排序）"""
        start_time = time.time()

        # 如果没有提供向量，需要先获取向量
        query_embedding = request.query_embedding
        if not query_embedding:
            # TODO: 调用 embedding 服务获取向量
            logger.warning("No query embedding provided, skipping vector search")
            vector_docs: List[RetrievalDocument] = []
        else:
            # 1. 并行执行向量检索和 BM25 检索
            vector_task = self.vector_service.search(
                query_embedding=query_embedding,
                top_k=settings.VECTOR_TOP_K,
                tenant_id=request.tenant_id,
                filters=request.filters,
            )
            bm25_task = self.bm25_service.search(
                query=request.query,
                top_k=settings.BM25_TOP_K,
                tenant_id=request.tenant_id,
                filters=request.filters,
            )

            vector_docs, bm25_docs = await asyncio.gather(vector_task, bm25_task)

        # 如果没有向量检索结果，仅执行 BM25
        if not query_embedding:
            bm25_docs = await self.bm25_service.search(
                query=request.query,
                top_k=settings.BM25_TOP_K,
                tenant_id=request.tenant_id,
                filters=request.filters,
            )
            vector_docs = []

        logger.info(f"Retrieved: vector={len(vector_docs)}, bm25={len(bm25_docs)}")

        # 2. RRF 融合
        top_k = request.top_k or settings.HYBRID_TOP_K
        fused_docs = await self.hybrid_service.fuse_results(
            vector_docs=vector_docs, bm25_docs=bm25_docs, top_k=top_k
        )

        # 3. 重排序（可选）
        reranked = False
        enable_rerank = request.enable_rerank if request.enable_rerank is not None else settings.ENABLE_RERANK

        if enable_rerank and fused_docs:
            rerank_top_k = request.rerank_top_k or settings.RERANK_TOP_K
            fused_docs = await self.rerank_service.rerank(
                query=request.query, documents=fused_docs, top_k=rerank_top_k
            )
            reranked = True

        latency_ms = (time.time() - start_time) * 1000

        return HybridResponse(
            documents=fused_docs,
            query=request.query,
            vector_count=len(vector_docs),
            bm25_count=len(bm25_docs),
            reranked=reranked,
            latency_ms=latency_ms,
        )
