"""
混合检索服务 - 三路并行检索
支持: Vector (语义检索) + BM25 (关键词检索) + Graph (图谱检索)
"""

import asyncio
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果"""
    document_id: str
    chunk_id: str
    content: str
    score: float
    source: str  # vector, bm25, graph
    metadata: dict


class HybridRetrievalService:
    """混合检索服务（三路并行）"""

    def __init__(
        self,
        vector_retriever=None,
        bm25_retriever=None,
        graph_retriever=None,
        fusion_method: str = "rrf",  # rrf, weighted, max
    ):
        """
        初始化混合检索服务

        Args:
            vector_retriever: 向量检索器
            bm25_retriever: BM25检索器
            graph_retriever: 图谱检索器
            fusion_method: 融合方法（rrf/weighted/max）
        """
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.graph_retriever = graph_retriever
        self.fusion_method = fusion_method

        # 检查至少有一个检索器
        if not any([vector_retriever, bm25_retriever, graph_retriever]):
            raise ValueError("At least one retriever must be provided")

        logger.info(
            f"Hybrid retrieval service initialized with fusion_method={fusion_method}, "
            f"retrievers=[vector={vector_retriever is not None}, "
            f"bm25={bm25_retriever is not None}, "
            f"graph={graph_retriever is not None}]"
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: str | None = None,
        filters: dict | None = None,
        weights: dict[str, float] | None = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_graph: bool = True,
    ) -> list[RetrievalResult]:
        """
        混合检索（三路并行）

        Args:
            query: 查询文本
            top_k: 返回结果数
            tenant_id: 租户ID
            filters: 过滤条件
            weights: 各路检索权重 {"vector": 0.4, "bm25": 0.3, "graph": 0.3}
            enable_vector: 是否启用向量检索
            enable_bm25: 是否启用BM25检索
            enable_graph: 是否启用图谱检索

        Returns:
            混合检索结果列表
        """
        start_time = time.time()

        # 默认权重
        if weights is None:
            weights = {
                "vector": 0.4,
                "bm25": 0.3,
                "graph": 0.3,
            }

        # 归一化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        # 准备检索任务
        tasks = []
        task_sources = []

        if enable_vector and self.vector_retriever:
            tasks.append(self._retrieve_vector(query, top_k * 2, tenant_id, filters))
            task_sources.append("vector")

        if enable_bm25 and self.bm25_retriever:
            tasks.append(self._retrieve_bm25(query, top_k * 2, tenant_id, filters))
            task_sources.append("bm25")

        if enable_graph and self.graph_retriever:
            tasks.append(self._retrieve_graph(query, top_k * 2, tenant_id, filters))
            task_sources.append("graph")

        if not tasks:
            logger.warning("No retrieval tasks enabled")
            return []

        # 并行执行所有检索任务
        logger.info(f"Starting parallel retrieval with {len(tasks)} tasks: {task_sources}")
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集各路结果
        all_results = {}
        for _i, (source, results) in enumerate(zip(task_sources, results_list, strict=False)):
            if isinstance(results, Exception):
                logger.error(f"{source} retrieval failed: {results}")
                all_results[source] = []
            else:
                all_results[source] = results
                logger.info(f"{source} retrieved {len(results)} results")

        # 融合结果
        fused_results = self._fuse_results(
            all_results=all_results,
            weights=weights,
            top_k=top_k,
        )

        elapsed = time.time() - start_time
        logger.info(
            f"Hybrid retrieval completed: {len(fused_results)} results in {elapsed:.3f}s "
            f"(fusion_method={self.fusion_method})"
        )

        return fused_results

    async def _retrieve_vector(
        self, query: str, top_k: int, tenant_id: str | None, filters: dict | None
    ) -> list[dict]:
        """向量检索"""
        try:
            results = await self.vector_retriever.retrieve(
                query=query,
                top_k=top_k,
                tenant_id=tenant_id,
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error(f"Vector retrieval error: {e}", exc_info=True)
            return []

    async def _retrieve_bm25(
        self, query: str, top_k: int, tenant_id: str | None, filters: dict | None
    ) -> list[dict]:
        """BM25 检索"""
        try:
            results = await self.bm25_retriever.retrieve(
                query=query,
                top_k=top_k,
                tenant_id=tenant_id,
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error(f"BM25 retrieval error: {e}", exc_info=True)
            return []

    async def _retrieve_graph(
        self, query: str, top_k: int, tenant_id: str | None, filters: dict | None
    ) -> list[dict]:
        """图谱检索"""
        try:
            results = await self.graph_retriever.retrieve(
                query=query,
                top_k=top_k,
                tenant_id=tenant_id,
                filters=filters,
            )
            return results
        except Exception as e:
            logger.error(f"Graph retrieval error: {e}", exc_info=True)
            return []

    def _fuse_results(
        self,
        all_results: dict[str, list[dict]],
        weights: dict[str, float],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        融合多路检索结果

        支持的融合方法:
        1. RRF (Reciprocal Rank Fusion) - 默认
        2. Weighted - 加权平均
        3. Max - 取最高分数
        """
        if self.fusion_method == "rrf":
            return self._fuse_rrf(all_results, top_k)
        elif self.fusion_method == "weighted":
            return self._fuse_weighted(all_results, weights, top_k)
        elif self.fusion_method == "max":
            return self._fuse_max(all_results, top_k)
        else:
            logger.warning(f"Unknown fusion method: {self.fusion_method}, using RRF")
            return self._fuse_rrf(all_results, top_k)

    def _fuse_rrf(self, all_results: dict[str, list[dict]], top_k: int, k: int = 60) -> list[RetrievalResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合

        公式: RRF_score(d) = Σ 1/(k + rank_i(d))
        其中 rank_i(d) 是文档 d 在第 i 路检索结果中的排名

        Args:
            all_results: 各路检索结果
            top_k: 返回数量
            k: RRF 参数（通常为60）
        """
        # 收集所有文档的 RRF 分数
        rrf_scores = {}
        doc_data = {}  # 保存文档数据

        for _source, results in all_results.items():
            for rank, result in enumerate(results, start=1):
                doc_id = result.get("document_id") or result.get("chunk_id")
                if not doc_id:
                    continue

                # 计算 RRF 分数
                rrf_score = 1.0 / (k + rank)

                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = 0.0
                    doc_data[doc_id] = result

                rrf_scores[doc_id] += rrf_score

        # 排序并返回
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        fused_results = []
        for doc_id, score in sorted_docs[:top_k]:
            data = doc_data[doc_id]
            fused_results.append(
                RetrievalResult(
                    document_id=data.get("document_id", ""),
                    chunk_id=data.get("chunk_id", doc_id),
                    content=data.get("text", data.get("content", "")),
                    score=score,
                    source="hybrid_rrf",
                    metadata=data.get("metadata", {}),
                )
            )

        return fused_results

    def _fuse_weighted(
        self, all_results: dict[str, list[dict]], weights: dict[str, float], top_k: int
    ) -> list[RetrievalResult]:
        """
        加权融合

        Formula: weighted_score(d) = Σ w_i * score_i(d)
        """
        # 收集所有文档的加权分数
        weighted_scores = {}
        doc_data = {}

        for source, results in all_results.items():
            weight = weights.get(source, 0.0)

            for result in results:
                doc_id = result.get("document_id") or result.get("chunk_id")
                if not doc_id:
                    continue

                score = result.get("score", 0.0)
                weighted_score = weight * score

                if doc_id not in weighted_scores:
                    weighted_scores[doc_id] = 0.0
                    doc_data[doc_id] = result

                weighted_scores[doc_id] += weighted_score

        # 排序并返回
        sorted_docs = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)

        fused_results = []
        for doc_id, score in sorted_docs[:top_k]:
            data = doc_data[doc_id]
            fused_results.append(
                RetrievalResult(
                    document_id=data.get("document_id", ""),
                    chunk_id=data.get("chunk_id", doc_id),
                    content=data.get("text", data.get("content", "")),
                    score=score,
                    source="hybrid_weighted",
                    metadata=data.get("metadata", {}),
                )
            )

        return fused_results

    def _fuse_max(self, all_results: dict[str, list[dict]], top_k: int) -> list[RetrievalResult]:
        """
        最大分数融合

        Formula: max_score(d) = max(score_i(d))
        """
        # 收集所有文档的最大分数
        max_scores = {}
        doc_data = {}

        for _source, results in all_results.items():
            for result in results:
                doc_id = result.get("document_id") or result.get("chunk_id")
                if not doc_id:
                    continue

                score = result.get("score", 0.0)

                if doc_id not in max_scores or score > max_scores[doc_id]:
                    max_scores[doc_id] = score
                    doc_data[doc_id] = result

        # 排序并返回
        sorted_docs = sorted(max_scores.items(), key=lambda x: x[1], reverse=True)

        fused_results = []
        for doc_id, score in sorted_docs[:top_k]:
            data = doc_data[doc_id]
            fused_results.append(
                RetrievalResult(
                    document_id=data.get("document_id", ""),
                    chunk_id=data.get("chunk_id", doc_id),
                    content=data.get("text", data.get("content", "")),
                    score=score,
                    source="hybrid_max",
                    metadata=data.get("metadata", {}),
                )
            )

        return fused_results

    async def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            "fusion_method": self.fusion_method,
            "retrievers": {
                "vector": self.vector_retriever is not None,
                "bm25": self.bm25_retriever is not None,
                "graph": self.graph_retriever is not None,
            },
        }

        # 获取各检索器的统计
        if self.vector_retriever and hasattr(self.vector_retriever, "get_stats"):
            stats["vector_stats"] = await self.vector_retriever.get_stats()

        if self.bm25_retriever and hasattr(self.bm25_retriever, "get_stats"):
            stats["bm25_stats"] = await self.bm25_retriever.get_stats()

        if self.graph_retriever and hasattr(self.graph_retriever, "get_stats"):
            stats["graph_stats"] = await self.graph_retriever.get_stats()

        return stats
