"""
Main retrieval orchestration service
"""

import asyncio
import logging
import time

from app.core.config import settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.models.retrieval import (
    BM25Request,
    BM25Response,
    GraphRequest,
    GraphResponse,
    HybridGraphRequest,
    HybridGraphResponse,
    HybridRequest,
    HybridResponse,
    RetrievalDocument,
    VectorRequest,
    VectorResponse,
)
from app.services.bm25_service import BM25Service
from app.services.embedding_service import EmbeddingService
from app.services.graph_retrieval_service import GraphRetrievalService
from app.services.hybrid_graph_service import HybridGraphService
from app.services.hybrid_service import HybridService
from app.services.query.expansion_service import QueryExpansionService
from app.services.rerank_service import RerankService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class RetrievalService:
    """检索编排服务"""

    def __init__(self):
        self.vector_service = VectorService()
        self.bm25_service = BM25Service()
        self.hybrid_service = HybridService(rrf_k=settings.RRF_K)
        self.rerank_service = RerankService()
        self.embedding_service = EmbeddingService()

        # 初始化Query Expansion Service (Task 1.1)
        try:
            self.query_expansion = QueryExpansionService(
                methods=["synonym", "spelling"],
                max_expansions=3,
                synonym_dict_path="data/synonyms.json",
            )
            logger.info("Query expansion service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize query expansion service: {e}")
            self.query_expansion = None

        # 初始化Neo4j客户端和Graph检索服务
        self.neo4j_client = None
        self.graph_service = None
        self.hybrid_graph_service = None

        if settings.ENABLE_GRAPH_RETRIEVAL:
            try:
                self.neo4j_client = Neo4jClient(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD,
                    database=settings.NEO4J_DATABASE,
                    max_connection_lifetime=settings.NEO4J_MAX_CONNECTION_LIFETIME,
                    max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                )
                self.graph_service = GraphRetrievalService(self.neo4j_client)
                self.hybrid_graph_service = HybridGraphService(
                    vector_service=self.vector_service,
                    bm25_service=self.bm25_service,
                    graph_service=self.graph_service,
                    rerank_service=self.rerank_service,
                    rrf_k=settings.RRF_K,
                )
                logger.info("Graph retrieval services initialized")
            except Exception as e:
                logger.error(f"Failed to initialize graph retrieval services: {e}")
                self.graph_service = None
                self.hybrid_graph_service = None

    async def startup(self):
        """启动时初始化连接"""
        if self.neo4j_client:
            try:
                await self.neo4j_client.connect()
                logger.info("Neo4j connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")

    async def shutdown(self):
        """关闭时清理连接"""
        if self.neo4j_client:
            try:
                await self.neo4j_client.close()
                logger.info("Neo4j connection closed")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {e}")

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
        """混合检索（向量 + BM25 + RRF融合 + 重排序 + 查询扩展）"""
        start_time = time.time()

        # 0. Query Expansion (Task 1.1) - 如果启用
        queries_to_search = [request.query]
        query_weights = [1.0]
        expansion_info = {
            "expanded": False,
            "queries": None,
            "latency_ms": None,
        }

        if request.enable_query_expansion and self.query_expansion:
            try:
                expanded = await self.query_expansion.expand(
                    query=request.query,
                    enable_llm=False,  # 默认不启用LLM（成本控制）
                )
                queries_to_search = expanded.expanded[: request.query_expansion_max]
                query_weights = expanded.weights[: request.query_expansion_max]
                expansion_info = {
                    "expanded": True,
                    "queries": queries_to_search,
                    "latency_ms": expanded.latency_ms,
                }
                logger.info(
                    f"Query expanded: {len(queries_to_search)} queries "
                    f"in {expanded.latency_ms:.1f}ms"
                )
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}, using original query")
                queries_to_search = [request.query]
                query_weights = [1.0]

        # 1. 对每个扩展查询执行检索
        all_vector_docs: list[RetrievalDocument] = []
        all_bm25_docs: list[RetrievalDocument] = []

        # 为每个查询生成embedding并检索
        for query, weight in zip(queries_to_search, query_weights, strict=False):
            # 获取query embedding
            query_embedding = None
            if not request.query_embedding:
                try:
                    query_embedding = await self.embedding_service.embed_query(query)
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for query '{query}': {e}")
            else:
                query_embedding = request.query_embedding

            # 并行执行向量检索和BM25检索
            if query_embedding:
                vector_task = self.vector_service.search(
                    query_embedding=query_embedding,
                    top_k=settings.VECTOR_TOP_K,
                    tenant_id=request.tenant_id,
                    filters=request.filters,
                )
                bm25_task = self.bm25_service.search(
                    query=query,
                    top_k=settings.BM25_TOP_K,
                    tenant_id=request.tenant_id,
                    filters=request.filters,
                )

                vector_docs, bm25_docs = await asyncio.gather(vector_task, bm25_task)

                # 根据权重调整分数
                for doc in vector_docs:
                    doc.score *= weight
                for doc in bm25_docs:
                    doc.score *= weight

                all_vector_docs.extend(vector_docs)
                all_bm25_docs.extend(bm25_docs)
            else:
                # 如果没有embedding，只执行BM25
                bm25_docs = await self.bm25_service.search(
                    query=query,
                    top_k=settings.BM25_TOP_K,
                    tenant_id=request.tenant_id,
                    filters=request.filters,
                )
                for doc in bm25_docs:
                    doc.score *= weight
                all_bm25_docs.extend(bm25_docs)

        logger.info(f"Retrieved: vector={len(all_vector_docs)}, bm25={len(all_bm25_docs)}")

        # 2. RRF 融合（去重）
        top_k = request.top_k or settings.HYBRID_TOP_K
        fused_docs = await self.hybrid_service.fuse_results(
            vector_docs=all_vector_docs, bm25_docs=all_bm25_docs, top_k=top_k
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
            vector_count=len(all_vector_docs),
            bm25_count=len(all_bm25_docs),
            reranked=reranked,
            latency_ms=latency_ms,
            query_expanded=expansion_info["expanded"],
            expanded_queries=expansion_info["queries"],
            expansion_latency_ms=expansion_info["latency_ms"],
        )

    async def graph_search(self, request: GraphRequest) -> GraphResponse:
        """图谱检索"""
        if not self.graph_service:
            raise RuntimeError("Graph retrieval is not enabled or initialization failed")

        start_time = time.time()

        # 执行图谱检索
        top_k = request.top_k or settings.GRAPH_TOP_K
        depth = request.depth or settings.GRAPH_DEPTH

        documents = await self.graph_service.search(
            query=request.query,
            top_k=top_k,
            depth=depth,
            tenant_id=request.tenant_id,
        )

        latency_ms = (time.time() - start_time) * 1000

        return GraphResponse(
            documents=documents,
            query=request.query,
            latency_ms=latency_ms,
        )

    async def hybrid_graph_search(self, request: HybridGraphRequest) -> HybridGraphResponse:
        """混合图谱检索（三路并行: Vector + BM25 + Graph）"""
        if not self.hybrid_graph_service:
            raise RuntimeError("Hybrid graph retrieval is not enabled or initialization failed")

        return await self.hybrid_graph_service.search(request)
