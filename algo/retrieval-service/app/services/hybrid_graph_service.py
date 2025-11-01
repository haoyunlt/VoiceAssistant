"""
混合图谱检索服务（三路并行: Vector + BM25 + Graph）
"""

import asyncio
import logging
import time

from app.core.config import settings
from app.models.retrieval import (
    HybridGraphRequest,
    HybridGraphResponse,
    RetrievalDocument,
)
from app.services.bm25_service import BM25Service
from app.services.graph_retrieval_service import GraphRetrievalService
from app.services.rerank_service import RerankService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class HybridGraphService:
    """混合图谱检索服务（三路并行）"""

    def __init__(
        self,
        vector_service: VectorService,
        bm25_service: BM25Service,
        graph_service: GraphRetrievalService,
        rerank_service: RerankService,
        rrf_k: int = 60,
    ):
        self.vector_service = vector_service
        self.bm25_service = bm25_service
        self.graph_service = graph_service
        self.rerank_service = rerank_service
        self.rrf_k = rrf_k

    async def search(self, request: HybridGraphRequest) -> HybridGraphResponse:
        """
        三路并行检索 + RRF融合 + 重排

        Args:
            request: 检索请求

        Returns:
            检索响应
        """
        start_time = time.time()
        stats = {}

        # Step 1: 三路并行检索
        vector_start = time.time()
        bm25_start = time.time()
        graph_start = time.time()

        # 并行执行三路检索
        results = await asyncio.gather(
            self._vector_retrieve(
                query_embedding=request.query_embedding,
                query=request.query,
                top_k=(request.top_k or settings.HYBRID_TOP_K) * 2,
                tenant_id=request.tenant_id,
                filters=request.filters,
            ),
            self._bm25_retrieve(
                query=request.query,
                top_k=(request.top_k or settings.HYBRID_TOP_K) * 2,
                tenant_id=request.tenant_id,
                filters=request.filters,
            ),
            self._graph_retrieve(
                query=request.query,
                top_k=(request.top_k or settings.HYBRID_TOP_K) * 2,
                depth=request.graph_depth or 2,
                tenant_id=request.tenant_id,
            ),
            return_exceptions=True,
        )

        # 处理结果和异常
        vector_results = results[0] if not isinstance(results[0], Exception) else []
        bm25_results = results[1] if not isinstance(results[1], Exception) else []
        graph_results = results[2] if not isinstance(results[2], Exception) else []

        # 记录异常
        if isinstance(results[0], Exception):
            logger.error(f"Vector检索失败: {results[0]}")
        if isinstance(results[1], Exception):
            logger.error(f"BM25检索失败: {results[1]}")
        if isinstance(results[2], Exception):
            logger.error(f"Graph检索失败: {results[2]}")

        stats["vector_time"] = time.time() - vector_start
        stats["bm25_time"] = time.time() - bm25_start
        stats["graph_time"] = time.time() - graph_start

        logger.info(
            f"三路检索完成: "
            f"vector={len(vector_results)}, "
            f"bm25={len(bm25_results)}, "
            f"graph={len(graph_results)}"
        )

        # Step 2: RRF融合
        fusion_start = time.time()
        weights = request.weights or {
            "vector": settings.HYBRID_VECTOR_WEIGHT,
            "bm25": settings.HYBRID_BM25_WEIGHT,
            "graph": settings.HYBRID_GRAPH_WEIGHT,
        }
        fused_results = self._rrf_fusion(
            {
                "vector": vector_results,
                "bm25": bm25_results,
                "graph": graph_results,
            },
            weights=weights,
            k=self.rrf_k,
        )
        stats["fusion_time"] = time.time() - fusion_start

        # Step 3: Cross-Encoder重排（可选）
        enable_rerank = (
            request.enable_rerank if request.enable_rerank is not None else settings.ENABLE_RERANK
        )

        if enable_rerank and len(fused_results) > 0:
            rerank_start = time.time()
            rerank_top_k = request.rerank_top_k or settings.RERANK_TOP_K
            reranked_results = await self.rerank_service.rerank(
                query=request.query, documents=fused_results, top_k=rerank_top_k
            )
            stats["rerank_time"] = time.time() - rerank_start
            final_results = reranked_results
            reranked = True
        else:
            top_k = request.top_k or settings.HYBRID_TOP_K
            final_results = fused_results[:top_k]
            stats["rerank_time"] = 0.0
            reranked = False

        elapsed_time = time.time() - start_time
        stats["total_time"] = elapsed_time

        return HybridGraphResponse(
            documents=final_results,
            query=request.query,
            vector_count=len(vector_results),
            bm25_count=len(bm25_results),
            graph_count=len(graph_results),
            reranked=reranked,
            latency_ms=elapsed_time * 1000,
            stats=stats,
        )

    async def _vector_retrieve(
        self,
        query_embedding: list[float],
        _query: str,
        top_k: int,
        tenant_id: str = None,
        filters: dict = None,
    ) -> list[RetrievalDocument]:
        """向量检索"""
        if not query_embedding:
            # 如果没有提供向量，可以在这里调用embedding服务生成
            # 为了简化，这里返回空列表
            logger.warning("No query embedding provided for vector search")
            return []

        return await self.vector_service.search(
            query_embedding=query_embedding,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
        )

    async def _bm25_retrieve(
        self,
        query: str,
        top_k: int,
        tenant_id: str = None,
        filters: dict = None,
    ) -> list[RetrievalDocument]:
        """BM25检索"""
        return await self.bm25_service.search(
            query=query, top_k=top_k, tenant_id=tenant_id, filters=filters
        )

    async def _graph_retrieve(
        self, query: str, top_k: int, depth: int, tenant_id: str = None
    ) -> list[RetrievalDocument]:
        """图谱检索"""
        return await self.graph_service.search(
            query=query, top_k=top_k, depth=depth, tenant_id=tenant_id
        )

    def _rrf_fusion(
        self,
        retrieval_results: dict[str, list[RetrievalDocument]],
        weights: dict[str, float],
        k: int = 60,
    ) -> list[RetrievalDocument]:
        """
        RRF融合算法（Reciprocal Rank Fusion）

        公式: score(d) = Σ weight_i / (k + rank_i(d))
        其中 k=60 是经验常数

        Args:
            retrieval_results: 各路检索结果
            weights: 权重配置
            k: RRF常数

        Returns:
            融合后的结果列表
        """
        doc_scores: dict[str, dict] = {}

        for source, results in retrieval_results.items():
            weight = weights.get(source, 1.0)

            for rank, result in enumerate(results):
                doc_key = f"{result.id}_{result.chunk_id}"

                # RRF分数
                rrf_score = weight / (k + rank + 1)

                if doc_key not in doc_scores:
                    doc_scores[doc_key] = {
                        "result": result,
                        "score": 0.0,
                        "sources": [],
                    }

                doc_scores[doc_key]["score"] += rrf_score
                doc_scores[doc_key]["sources"].append(source)

        # 排序
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)

        # 更新分数并标记来源
        fused_results = []
        for doc in sorted_docs:
            result = doc["result"]
            result.score = doc["score"]
            result.source = "fusion" if len(doc["sources"]) > 1 else doc["sources"][0]
            # 在metadata中记录融合来源
            if not result.metadata:
                result.metadata = {}
            result.metadata["fusion_sources"] = doc["sources"]
            fused_results.append(result)

        logger.info(f"RRF融合后: {len(fused_results)} 条结果")
        return fused_results
