"""
RetrievalService - 核心检索服务

整合多种检索方式：
- 向量检索 (Milvus)
- BM25 检索
- 图谱检索 (Neo4j)
- 混合检索 (RRF)
- 重排序 (Cross-Encoder)
"""

import hashlib
import logging
from typing import Dict, List, Optional

from app.core.bm25_retriever import BM25Retriever
from app.core.graph_retriever import GraphRetriever
from app.core.reranker import CrossEncoderReranker
from app.core.vector_retriever import VectorRetriever
from app.infrastructure.redis_cache import RedisCache

logger = logging.getLogger(__name__)


class RetrievalService:
    """检索服务"""

    def __init__(self):
        """初始化检索服务"""
        # 检索器
        self.vector_retriever = None
        self.bm25_retriever = None
        self.graph_retriever = None

        # 重排序器
        self.reranker = None

        # 缓存
        self.cache = None

        # 统计信息
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "vector_retrievals": 0,
            "bm25_retrievals": 0,
            "graph_retrievals": 0,
            "hybrid_retrievals": 0,
            "rerank_operations": 0,
        }

        logger.info("Retrieval service initialized")

    async def initialize(self):
        """初始化所有组件"""
        logger.info("Initializing retrieval components...")

        # 初始化检索器
        self.vector_retriever = VectorRetriever()
        await self.vector_retriever.initialize()

        self.bm25_retriever = BM25Retriever()
        await self.bm25_retriever.initialize()

        self.graph_retriever = GraphRetriever()
        await self.graph_retriever.initialize()

        # 初始化重排序器
        self.reranker = CrossEncoderReranker()
        await self.reranker.initialize()

        # 初始化缓存
        self.cache = RedisCache()
        await self.cache.initialize()

        logger.info("All retrieval components initialized successfully")

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "hybrid",
        tenant_id: str = None,
        filters: Dict = None,
        rerank: bool = True,
    ) -> List[Dict]:
        """
        检索接口

        Args:
            query: 查询文本
            top_k: 返回结果数
            mode: 检索模式 (vector/bm25/graph/hybrid)
            tenant_id: 租户 ID
            filters: 过滤条件
            rerank: 是否重排序

        Returns:
            检索结果列表
        """
        self.stats["total_queries"] += 1

        # 检查缓存
        cache_key = self._generate_cache_key(query, top_k, mode, tenant_id)
        cached_results = await self._get_from_cache(cache_key)
        if cached_results is not None:
            self.stats["cache_hits"] += 1
            logger.info(f"Cache hit for query: {query[:50]}...")
            return cached_results

        self.stats["cache_misses"] += 1

        # 根据模式执行检索
        if mode == "vector":
            results = await self._vector_retrieve(query, top_k, tenant_id, filters)
            self.stats["vector_retrievals"] += 1

        elif mode == "bm25":
            results = await self._bm25_retrieve(query, top_k, tenant_id, filters)
            self.stats["bm25_retrievals"] += 1

        elif mode == "graph":
            results = await self._graph_retrieve(query, top_k, tenant_id, filters)
            self.stats["graph_retrievals"] += 1

        elif mode == "hybrid":
            results = await self._hybrid_retrieve(query, top_k, tenant_id, filters)
            self.stats["hybrid_retrievals"] += 1

        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

        # 重排序
        if rerank and len(results) > 0:
            results = await self._rerank(query, results, top_k)
            self.stats["rerank_operations"] += 1

        # 写入缓存
        await self._set_to_cache(cache_key, results)

        logger.info(f"Retrieved {len(results)} results for query: {query[:50]}...")

        return results

    async def _vector_retrieve(
        self, query: str, top_k: int, tenant_id: str, filters: Dict
    ) -> List[Dict]:
        """向量检索"""
        return await self.vector_retriever.retrieve(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
        )

    async def _bm25_retrieve(
        self, query: str, top_k: int, tenant_id: str, filters: Dict
    ) -> List[Dict]:
        """BM25 检索"""
        return await self.bm25_retriever.retrieve(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
        )

    async def _graph_retrieve(
        self, query: str, top_k: int, tenant_id: str, filters: Dict
    ) -> List[Dict]:
        """图谱检索"""
        return await self.graph_retriever.retrieve(
            query=query,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
        )

    async def _hybrid_retrieve(
        self, query: str, top_k: int, tenant_id: str, filters: Dict
    ) -> List[Dict]:
        """
        混合检索（RRF - Reciprocal Rank Fusion）

        同时执行向量检索和 BM25 检索，使用 RRF 融合结果
        """
        # 并行执行多种检索
        import asyncio

        vector_results, bm25_results = await asyncio.gather(
            self._vector_retrieve(query, top_k * 2, tenant_id, filters),
            self._bm25_retrieve(query, top_k * 2, tenant_id, filters),
        )

        # RRF 融合
        fused_results = self._rrf_fusion(
            [vector_results, bm25_results],
            top_k=top_k,
        )

        return fused_results

    def _rrf_fusion(self, results_list: List[List[Dict]], top_k: int, k: int = 60) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF)

        公式: RRF(d) = Σ 1/(k + rank_i(d))

        Args:
            results_list: 多个检索结果列表
            top_k: 返回结果数
            k: RRF 常数（默认 60）

        Returns:
            融合后的结果列表
        """
        # 计算每个文档的 RRF 分数
        doc_scores = {}

        for results in results_list:
            for rank, result in enumerate(results, 1):
                doc_id = result.get("chunk_id") or result.get("doc_id")

                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "score": 0,
                        "data": result,
                    }

                # RRF 公式
                doc_scores[doc_id]["score"] += 1 / (k + rank)

        # 按分数排序
        sorted_docs = sorted(
            doc_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )

        # 取 Top K
        results = []
        for doc_id, doc_info in sorted_docs[:top_k]:
            result = doc_info["data"].copy()
            result["rrf_score"] = doc_info["score"]
            results.append(result)

        logger.info(f"RRF fusion: {len(results_list)} sources → {len(results)} results")

        return results

    async def _rerank(self, query: str, results: List[Dict], top_k: int) -> List[Dict]:
        """重排序"""
        if not results:
            return results

        # 使用 Cross-Encoder 重排序
        reranked = await self.reranker.rerank(
            query=query,
            documents=results,
            top_k=top_k,
        )

        return reranked

    def _generate_cache_key(
        self, query: str, top_k: int, mode: str, tenant_id: str
    ) -> str:
        """生成缓存键"""
        key_str = f"{query}:{top_k}:{mode}:{tenant_id or 'default'}"
        hash_key = hashlib.md5(key_str.encode()).hexdigest()
        return f"retrieval:cache:{hash_key}"

    async def _get_from_cache(self, key: str) -> Optional[List[Dict]]:
        """从缓存获取"""
        if not self.cache:
            return None
        return await self.cache.get(key)

    async def _set_to_cache(self, key: str, value: List[Dict]):
        """写入缓存"""
        if not self.cache:
            return
        await self.cache.set(key, value, ttl=3600)  # 1 小时

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        cache_hit_rate = (
            self.stats["cache_hits"] / self.stats["total_queries"]
            if self.stats["total_queries"] > 0
            else 0
        )

        return {
            **self.stats,
            "cache_hit_rate": cache_hit_rate,
            "vector_store_entities": await self.vector_retriever.count() if self.vector_retriever else 0,
            "bm25_documents": await self.bm25_retriever.count() if self.bm25_retriever else 0,
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up retrieval service...")

        if self.vector_retriever:
            await self.vector_retriever.cleanup()

        if self.bm25_retriever:
            await self.bm25_retriever.cleanup()

        if self.graph_retriever:
            await self.graph_retriever.cleanup()

        if self.cache:
            await self.cache.cleanup()

        logger.info("Retrieval service cleanup complete")

    # 便捷属性
    @property
    def vector_store_client(self):
        return self.vector_retriever.vector_store_client if self.vector_retriever else None

    @property
    def neo4j_client(self):
        return self.graph_retriever.neo4j_client if self.graph_retriever else None

    @property
    def redis_client(self):
        return self.cache.redis_client if self.cache else None
