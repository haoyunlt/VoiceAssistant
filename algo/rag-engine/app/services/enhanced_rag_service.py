"""
Enhanced RAG Service v2.0

整合所有优化组件：
- 混合检索（Vector + BM25 + RRF）
- Cross-Encoder 重排
- FAISS 语义缓存
- Prometheus 可观测性
"""

import logging
import time
from typing import Any

from app.observability.metrics import RAGMetrics, record_cache_hit, record_cache_miss
from app.reranking.reranker import get_reranker
from app.retrieval.hybrid_retriever import get_hybrid_retriever
from app.services.semantic_cache_service import SemanticCacheService

logger = logging.getLogger(__name__)


class EnhancedRAGService:
    """增强型 RAG 服务 v2.0"""

    def __init__(
        self,
        retrieval_client,  # 向量检索客户端
        llm_client,  # LLM 客户端
        enable_hybrid: bool = True,
        enable_rerank: bool = True,
        enable_cache: bool = True,
    ):
        """
        初始化增强型 RAG 服务

        Args:
            retrieval_client: 向量检索客户端
            llm_client: LLM 客户端
            enable_hybrid: 启用混合检索
            enable_rerank: 启用重排
            enable_cache: 启用语义缓存
        """
        self.retrieval_client = retrieval_client
        self.llm_client = llm_client

        # 混合检索器
        self.enable_hybrid = enable_hybrid
        self.hybrid_retriever = get_hybrid_retriever() if enable_hybrid else None

        # 重排器
        self.enable_rerank = enable_rerank
        self.reranker = get_reranker() if enable_rerank else None

        # 语义缓存
        self.enable_cache = enable_cache
        self.cache_service = None
        if enable_cache:
            try:
                self.cache_service = SemanticCacheService(
                    similarity_threshold=0.92,
                    use_faiss=True,
                )
                logger.info("Semantic cache initialized with FAISS")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic cache: {e}")
                self.cache_service = None

        logger.info(
            f"Enhanced RAG Service initialized: hybrid={enable_hybrid}, rerank={enable_rerank}, cache={enable_cache}"
        )

    async def query(
        self,
        query: str,
        tenant_id: str,
        mode: str = "advanced",
        top_k: int = 5,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """
        增强型 RAG 查询

        Args:
            query: 用户查询
            tenant_id: 租户 ID
            mode: 模式（simple/advanced/precise）
            top_k: 返回文档数
            temperature: LLM 温度

        Returns:
            查询结果
        """
        # 使用指标收集器
        with RAGMetrics(mode=mode, tenant_id=tenant_id) as metrics:
            try:
                # 1. 检查语义缓存
                if self.enable_cache and self.cache_service:
                    cached_result = await self._check_cache(query, tenant_id)
                    if cached_result:
                        record_cache_hit(tenant_id)
                        metrics.record_answer(cached_result["answer"])
                        return cached_result
                    record_cache_miss(tenant_id)

                # 2. 执行检索（混合检索）
                retrieval_start = time.time()
                documents = await self._retrieve_documents(query, tenant_id, top_k * 2, mode)
                retrieval_latency_ms = (time.time() - retrieval_start) * 1000

                strategy = "hybrid" if self.enable_hybrid else "vector"
                metrics.record_retrieval(strategy, retrieval_latency_ms, len(documents))

                logger.info(f"Retrieved {len(documents)} documents in {retrieval_latency_ms:.2f}ms")

                # 3. 重排序
                if self.enable_rerank and self.reranker and documents:
                    rerank_start = time.time()
                    documents = self.reranker.rerank(query, documents)
                    rerank_latency_ms = (time.time() - rerank_start) * 1000

                    avg_score = sum(doc.get("rerank_score", 0) for doc in documents) / len(
                        documents
                    )
                    metrics.record_rerank("cross-encoder", rerank_latency_ms, avg_score)

                    logger.info(
                        f"Reranked to {len(documents)} documents in {rerank_latency_ms:.2f}ms"
                    )

                # 4. 取 top-k
                documents = documents[:top_k]

                # 5. 构建上下文
                context = self._build_context(documents)

                # 6. 生成答案
                llm_start = time.time()
                answer = await self._generate_answer(query, context, temperature)
                llm_latency_ms = (time.time() - llm_start) * 1000

                # 估算 token 使用（简化）
                estimated_tokens = len(context) // 4 + len(answer) // 4
                metrics.record_llm("gpt-4-turbo", llm_latency_ms, estimated_tokens)
                metrics.record_answer(answer)

                # 7. 提取来源
                sources = self._extract_sources(documents)

                # 8. 缓存结果
                if self.enable_cache and self.cache_service:
                    await self._set_cache(query, answer, sources)

                # 9. 返回结果
                result = {
                    "answer": answer,
                    "sources": sources,
                    "query": query,
                    "retrieved_count": len(documents),
                    "mode": mode,
                    "from_cache": False,
                    "metrics": {
                        "retrieval_latency_ms": retrieval_latency_ms,
                        "rerank_latency_ms": rerank_latency_ms if self.enable_rerank else 0,
                        "llm_latency_ms": llm_latency_ms,
                    },
                }

                return result

            except Exception as e:
                logger.error(f"Enhanced RAG query failed: {e}", exc_info=True)
                raise

    async def _check_cache(self, query: str, _tenant_id: str) -> dict[str, Any] | None:
        """检查语义缓存"""
        try:
            cached_answer = await self.cache_service.get_cached_answer(query)
            if cached_answer:
                logger.info(
                    f"Cache HIT: {query[:50]}... (similarity={cached_answer.similarity:.4f})"
                )
                return {
                    "answer": cached_answer.answer,
                    "sources": cached_answer.sources,
                    "query": query,
                    "original_query": cached_answer.original_query,
                    "from_cache": True,
                    "cache_similarity": cached_answer.similarity,
                }
            return None
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return None

    async def _set_cache(self, query: str, answer: str, sources: list[dict]):
        """设置缓存"""
        try:
            await self.cache_service.set_cached_answer(query, answer, sources)
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def _retrieve_documents(
        self, query: str, tenant_id: str, top_k: int, _mode: str
    ) -> list[dict[str, Any]]:
        """执行检索（混合检索）"""
        # 1. 向量检索
        vector_results = await self.retrieval_client.vector_search(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
        )

        # 2. 如果启用混合检索，融合 BM25
        if self.enable_hybrid and self.hybrid_retriever:
            try:
                # 混合检索器会调用 BM25 并融合结果
                results = self.hybrid_retriever.retrieve(
                    query=query,
                    vector_results=vector_results,
                    top_k=top_k,
                    fusion_method="rrf",  # 使用 RRF 融合
                )
                logger.info(f"Hybrid retrieval: {len(results)} documents")
                return results
            except Exception as e:
                logger.warning(f"Hybrid retrieval failed, falling back to vector only: {e}")
                return vector_results[:top_k]
        else:
            return vector_results[:top_k]

    def _build_context(self, documents: list[dict[str, Any]]) -> str:
        """构建上下文"""
        context_parts = []
        for i, doc in enumerate(documents, 1):
            content = doc.get("text", "") or doc.get("content", "")
            score = doc.get("rerank_score") or doc.get("rrf_score") or doc.get("score", 0)
            context_parts.append(f"[文档{i}] (相关度: {score:.3f})\n{content}")

        return "\n\n".join(context_parts)

    async def _generate_answer(self, query: str, context: str, temperature: float) -> str:
        """生成答案"""
        prompt = f"""基于以下文档回答问题。如果文档中没有相关信息，请说明。

问题：{query}

文档：
{context}

回答："""

        answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=2000,
        )

        return answer.strip()

    def _extract_sources(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """提取来源"""
        sources = []
        for doc in documents:
            sources.append(
                {
                    "document_id": doc.get("document_id") or doc.get("id"),
                    "content": doc.get("content", doc.get("text", ""))[:200],
                    "score": doc.get("rerank_score") or doc.get("rrf_score") or doc.get("score"),
                }
            )
        return sources

    async def get_stats(self) -> dict[str, Any]:
        """获取服务统计信息"""
        stats = {
            "enabled_features": {
                "hybrid_retrieval": self.enable_hybrid,
                "reranking": self.enable_rerank,
                "semantic_cache": self.enable_cache,
            }
        }

        # 缓存统计
        if self.cache_service:
            cache_stats = await self.cache_service.get_cache_stats()
            stats["cache_stats"] = cache_stats

        # 混合检索健康检查
        if self.hybrid_retriever:
            stats["hybrid_retrieval_health"] = self.hybrid_retriever.health_check()

        # 重排器健康检查
        if self.reranker:
            stats["reranker_health"] = self.reranker.health_check()

        return stats


# 全局实例
_enhanced_rag_service: EnhancedRAGService | None = None


def get_enhanced_rag_service(
    retrieval_client,
    llm_client,
    enable_hybrid: bool = True,
    enable_rerank: bool = True,
    enable_cache: bool = True,
) -> EnhancedRAGService:
    """
    获取增强型 RAG 服务实例

    Args:
        retrieval_client: 向量检索客户端
        llm_client: LLM 客户端
        enable_hybrid: 启用混合检索
        enable_rerank: 启用重排
        enable_cache: 启用语义缓存

    Returns:
        EnhancedRAGService 实例
    """
    global _enhanced_rag_service

    if _enhanced_rag_service is None:
        _enhanced_rag_service = EnhancedRAGService(
            retrieval_client=retrieval_client,
            llm_client=llm_client,
            enable_hybrid=enable_hybrid,
            enable_rerank=enable_rerank,
            enable_cache=enable_cache,
        )

    return _enhanced_rag_service
