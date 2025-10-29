"""
Advanced RAG Service - 高级 RAG 服务

集成 Graph RAG 和 Query Decomposition（Iter 2 功能）
"""

import asyncio
import logging
import time
from typing import Any

from app.graph.entity_extractor import EntityExtractor
from app.graph.graph_retriever import GraphRetriever
from app.graph.graph_store import get_graph_store
from app.observability.metrics import RAGMetrics
from app.query.query_classifier import QueryClassifier
from app.query.query_decomposer import QueryDecomposer
from app.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)


class AdvancedRAGService:
    """高级 RAG 服务（支持 Graph RAG 和 Query Decomposition）"""

    def __init__(
        self,
        base_rag_service: EnhancedRAGService,
        llm_client,
        enable_graph: bool = True,
        enable_decomposition: bool = True,
        graph_backend: str = "networkx",
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
    ):
        """
        初始化高级 RAG 服务

        Args:
            base_rag_service: 基础 RAG 服务（Iter 1）
            llm_client: LLM 客户端
            enable_graph: 启用图谱检索
            enable_decomposition: 启用查询分解
            graph_backend: 图谱后端（networkx/neo4j）
            neo4j_uri: Neo4j URI
            neo4j_user: Neo4j 用户名
            neo4j_password: Neo4j 密码
        """
        self.base_rag_service = base_rag_service
        self.llm_client = llm_client

        # Graph RAG
        self.enable_graph = enable_graph
        if enable_graph:
            try:
                self.graph_store = get_graph_store(
                    backend=graph_backend,
                    neo4j_uri=neo4j_uri,
                    neo4j_user=neo4j_user,
                    neo4j_password=neo4j_password,
                )
                self.graph_retriever = GraphRetriever(self.graph_store)
                self.entity_extractor = EntityExtractor(llm_client)
                logger.info(f"Graph RAG enabled with {graph_backend} backend")
            except Exception as e:
                logger.warning(f"Failed to initialize Graph RAG: {e}")
                self.enable_graph = False

        # Query Decomposition
        self.enable_decomposition = enable_decomposition
        if enable_decomposition:
            self.query_decomposer = QueryDecomposer(llm_client)
            self.query_classifier = QueryClassifier(llm_client)
            logger.info("Query Decomposition enabled")

        logger.info(
            f"Advanced RAG Service initialized: graph={enable_graph}, decomposition={enable_decomposition}"
        )

    async def query(
        self,
        query: str,
        tenant_id: str = "default",
        top_k: int = 5,
        mode: str = "advanced",
        temperature: float = 0.7,
        use_graph: bool = True,
        use_decomposition: bool = True,
    ) -> dict[str, Any]:
        """
        高级 RAG 查询

        Args:
            query: 用户查询
            tenant_id: 租户 ID
            top_k: 返回文档数
            mode: 查询模式
            temperature: LLM 温度
            use_graph: 使用图谱检索
            use_decomposition: 使用查询分解

        Returns:
            查询结果
        """
        with RAGMetrics(mode=mode, tenant_id=tenant_id) as metrics:
            try:
                # 1. 查询分类
                query_analysis = None
                if self.enable_decomposition:
                    query_analysis = await self.query_classifier.classify(query)
                    logger.info(
                        f"Query analysis: type={query_analysis.get('type')}, "
                        f"complexity={query_analysis.get('complexity')}"
                    )

                # 2. 检查是否需要查询分解
                should_decompose = (
                    self.enable_decomposition
                    and use_decomposition
                    and query_analysis
                    and query_analysis.get("complexity", 5) >= 7
                )

                if should_decompose:
                    logger.info("Using query decomposition strategy")
                    return await self._query_with_decomposition(
                        query, tenant_id, top_k, mode, temperature, query_analysis, metrics
                    )

                # 3. 检查是否使用图谱检索
                use_graph_retrieval = (
                    self.enable_graph
                    and use_graph
                    and query_analysis
                    and query_analysis.get("type") in ["multi_hop", "complex_reasoning"]
                )

                if use_graph_retrieval:
                    logger.info("Using graph-enhanced retrieval")
                    return await self._query_with_graph(
                        query, tenant_id, top_k, mode, temperature, query_analysis, metrics
                    )

                # 4. 使用基础 RAG
                logger.info("Using base RAG service")
                return await self.base_rag_service.query(
                    query=query, tenant_id=tenant_id, top_k=top_k, mode=mode, temperature=temperature
                )

            except Exception as e:
                logger.error(f"Advanced RAG query failed: {e}", exc_info=True)
                raise

    async def _query_with_graph(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        mode: str,
        temperature: float,
        query_analysis: dict[str, Any],
        metrics: RAGMetrics,
    ) -> dict[str, Any]:
        """使用图谱增强的 RAG 查询"""
        # 1. 提取查询中的实体
        entities, relations = await self.entity_extractor.extract_entities_and_relations(
            query, use_llm=False
        )
        entity_names = [e["name"] for e in entities[:5]]  # 限制实体数量

        logger.info(f"Extracted entities: {entity_names}")

        # 2. 并行检索：向量检索 + 图谱检索
        graph_start = time.time()
        vector_results, graph_results = await asyncio.gather(
            self.base_rag_service._retrieve_documents(query, tenant_id, top_k * 2, mode),
            self.graph_retriever.query(query, entity_names, max_hops=2, top_k=top_k),
            return_exceptions=True,
        )
        graph_latency_ms = (time.time() - graph_start) * 1000

        # 处理检索异常
        if isinstance(vector_results, Exception):
            logger.error(f"Vector retrieval failed: {vector_results}")
            vector_results = []

        if isinstance(graph_results, Exception):
            logger.error(f"Graph retrieval failed: {graph_results}")
            graph_results = []

        logger.info(
            f"Retrieved {len(vector_results)} vector docs + {len(graph_results)} graph nodes in {graph_latency_ms:.2f}ms"
        )

        # 3. 合并结果
        all_documents = self._merge_retrieval_results(vector_results, graph_results)

        # 4. 重排（如果启用）
        if self.base_rag_service.enable_rerank and self.base_rag_service.reranker:
            rerank_start = time.time()
            all_documents = self.base_rag_service.reranker.rerank(query, all_documents[:top_k * 2])
            rerank_latency_ms = (time.time() - rerank_start) * 1000
            avg_score = sum(doc.get("rerank_score", 0) for doc in all_documents) / max(
                len(all_documents), 1
            )
            metrics.record_rerank("cross-encoder", rerank_latency_ms, avg_score)

        # 5. 取 top-k
        final_documents = all_documents[:top_k]

        # 6. 生成答案
        context = self.base_rag_service._build_context(final_documents)
        answer = await self.base_rag_service._generate_answer(query, context, temperature)

        # 7. 缓存结果
        if self.base_rag_service.enable_cache and self.base_rag_service.cache_service:
            sources = self.base_rag_service._extract_sources(final_documents)
            await self.base_rag_service.cache_service.set_cached_answer(
                query, answer, sources=sources
            )

        return {
            "answer": answer,
            "documents": final_documents,
            "sources": self.base_rag_service._extract_sources(final_documents),
            "strategy": "graph_enhanced",
            "entities": entity_names,
            "graph_results_count": len(graph_results),
        }

    async def _query_with_decomposition(
        self,
        query: str,
        tenant_id: str,
        top_k: int,
        mode: str,
        temperature: float,
        query_analysis: dict[str, Any],
        metrics: RAGMetrics,
    ) -> dict[str, Any]:
        """使用查询分解的 RAG 查询"""
        # 1. 分解查询
        decompose_start = time.time()
        sub_queries = await self.query_decomposer.decompose(
            query, max_sub_queries=4, query_analysis=query_analysis
        )
        decompose_latency_ms = (time.time() - decompose_start) * 1000

        logger.info(
            f"Decomposed into {len(sub_queries)} sub-queries in {decompose_latency_ms:.2f}ms"
        )

        # 2. 并行处理子查询
        sub_query_start = time.time()
        sub_query_tasks = [
            self.base_rag_service.query(
                query=sub_q, tenant_id=tenant_id, top_k=top_k, mode=mode, temperature=temperature
            )
            for sub_q in sub_queries
        ]
        sub_results = await asyncio.gather(*sub_query_tasks, return_exceptions=True)
        sub_query_latency_ms = (time.time() - sub_query_start) * 1000

        logger.info(f"Completed {len(sub_queries)} sub-queries in {sub_query_latency_ms:.2f}ms")

        # 3. 提取子答案
        sub_answers = []
        all_documents = []
        for i, result in enumerate(sub_results):
            if isinstance(result, Exception):
                logger.error(f"Sub-query {i} failed: {result}")
                sub_answers.append(f"[子查询失败: {sub_queries[i]}]")
            else:
                sub_answers.append(result.get("answer", ""))
                all_documents.extend(result.get("documents", []))

        # 4. 合并答案
        merge_start = time.time()
        merged_answer = await self.query_decomposer.merge_answers(
            sub_queries, sub_answers, query
        )
        merge_latency_ms = (time.time() - merge_start) * 1000

        logger.info(f"Merged answers in {merge_latency_ms:.2f}ms")

        # 5. 去重文档
        unique_documents = self._deduplicate_documents(all_documents)[:top_k]

        return {
            "answer": merged_answer,
            "documents": unique_documents,
            "sources": self.base_rag_service._extract_sources(unique_documents),
            "strategy": "query_decomposition",
            "sub_queries": sub_queries,
            "sub_answers": sub_answers,
        }

    def _merge_retrieval_results(
        self, vector_results: list[dict], graph_results: list[dict]
    ) -> list[dict]:
        """合并向量检索和图谱检索结果"""
        merged = []

        # 添加向量检索结果
        for doc in vector_results:
            doc["source_type"] = "vector"
            merged.append(doc)

        # 添加图谱检索结果（转换格式）
        for graph_node in graph_results:
            doc = {
                "id": graph_node.get("entity", "") + "_graph",
                "content": graph_node.get("content", ""),
                "score": graph_node.get("score", 0.5),
                "source_type": "graph",
                "entity": graph_node.get("entity"),
                "neighbor": graph_node.get("neighbor", {}).get("id"),
                "relation": graph_node.get("relation"),
                "hop": graph_node.get("hop", 1),
            }
            merged.append(doc)

        # 按分数排序
        merged = sorted(merged, key=lambda x: x.get("score", 0), reverse=True)

        return merged

    def _deduplicate_documents(self, documents: list[dict]) -> list[dict]:
        """去重文档"""
        seen_ids = set()
        unique_docs = []

        for doc in documents:
            doc_id = doc.get("id") or doc.get("document_id")
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_docs.append(doc)

        return unique_docs


# 全局实例
_advanced_rag_service: AdvancedRAGService | None = None


def get_advanced_rag_service(
    base_rag_service: EnhancedRAGService,
    llm_client,
    enable_graph: bool = True,
    enable_decomposition: bool = True,
    graph_backend: str = "networkx",
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
) -> AdvancedRAGService:
    """
    获取高级 RAG 服务实例

    Args:
        base_rag_service: 基础 RAG 服务
        llm_client: LLM 客户端
        enable_graph: 启用图谱检索
        enable_decomposition: 启用查询分解
        graph_backend: 图谱后端
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j 用户名
        neo4j_password: Neo4j 密码

    Returns:
        AdvancedRAGService 实例
    """
    global _advanced_rag_service

    if _advanced_rag_service is None:
        _advanced_rag_service = AdvancedRAGService(
            base_rag_service=base_rag_service,
            llm_client=llm_client,
            enable_graph=enable_graph,
            enable_decomposition=enable_decomposition,
            graph_backend=graph_backend,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
        )

    return _advanced_rag_service

