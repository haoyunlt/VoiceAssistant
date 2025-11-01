"""
Ultimate RAG Service - 终极 RAG 服务

集成所有优化功能：
- Iter 1: Hybrid Retrieval + Reranking + Semantic Cache + Observability
- Iter 2: Graph RAG + Query Decomposition
- Iter 3: Self-RAG + Context Compression
- Iter 4: Agentic RAG (ReAct + Tool Calling)
"""

import logging
from typing import Any

from app.agent.react_agent import ReactAgent
from app.agent.tools import (
    CalculatorTool,
    CodeInterpreterTool,
    GraphQueryTool,
    SQLQueryTool,
    VectorSearchTool,
    WebSearchTool,
)
from app.compression.context_compressor import ContextCompressor
from app.observability.agent_metrics import AgentMetrics
from app.observability.metrics import RAGMetrics
from app.self_rag.hallucination_detector import HallucinationDetector
from app.self_rag.self_rag_service import SelfRAGService
from app.services.advanced_rag_service import AdvancedRAGService
from app.services.enhanced_rag_service import EnhancedRAGService

logger = logging.getLogger(__name__)


class UltimateRAGService:
    """终极 RAG 服务（集成所有优化功能）"""

    def __init__(
        self,
        retrieval_client,
        llm_client,
        # Iter 1: 基础增强
        enable_hybrid: bool = True,
        enable_rerank: bool = True,
        enable_cache: bool = True,
        # Iter 2: 高级检索
        enable_graph: bool = True,
        enable_decomposition: bool = True,
        graph_backend: str = "networkx",
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        # Iter 3: 质量与成本
        enable_self_rag: bool = True,
        enable_compression: bool = True,
        compression_ratio: float = 0.5,
        use_llmlingua: bool = False,
        # Iter 4: Agentic RAG
        enable_agent: bool = True,
        agent_max_iterations: int = 10,
    ):
        """
        初始化终极 RAG 服务

        Args:
            retrieval_client: 向量检索客户端
            llm_client: LLM 客户端
            enable_hybrid: 启用混合检索
            enable_rerank: 启用重排
            enable_cache: 启用语义缓存
            enable_graph: 启用图谱检索
            enable_decomposition: 启用查询分解
            graph_backend: 图谱后端
            neo4j_uri: Neo4j URI
            neo4j_user: Neo4j 用户名
            neo4j_password: Neo4j 密码
            enable_self_rag: 启用自我纠错
            enable_compression: 启用上下文压缩
            compression_ratio: 压缩比例
            use_llmlingua: 使用 LLMLingua
        """
        # Iter 1: 基础增强 RAG
        self.base_rag = EnhancedRAGService(
            retrieval_client=retrieval_client,
            llm_client=llm_client,
            enable_hybrid=enable_hybrid,
            enable_rerank=enable_rerank,
            enable_cache=enable_cache,
        )

        # Iter 2: 高级 RAG（Graph + Decomposition）
        self.advanced_rag = AdvancedRAGService(
            base_rag_service=self.base_rag,
            llm_client=llm_client,
            enable_graph=enable_graph,
            enable_decomposition=enable_decomposition,
            graph_backend=graph_backend,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
        )

        # Iter 3: Self-RAG
        self.enable_self_rag = enable_self_rag
        if enable_self_rag:
            try:
                hallucination_detector = HallucinationDetector(llm_client, use_nli=False)
                self.self_rag = SelfRAGService(
                    llm_client=llm_client,
                    hallucination_detector=hallucination_detector,
                    max_refinement_attempts=2,
                )
                logger.info("Self-RAG enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Self-RAG: {e}")
                self.enable_self_rag = False

        # Iter 3: Context Compression
        self.enable_compression = enable_compression
        self.compression_ratio = compression_ratio
        if enable_compression:
            try:
                self.compressor = ContextCompressor(use_llmlingua=use_llmlingua)
                logger.info(f"Context compression enabled (ratio={compression_ratio})")
            except Exception as e:
                logger.warning(f"Failed to initialize compressor: {e}")
                self.enable_compression = False

        # Iter 4: Agentic RAG
        self.enable_agent = enable_agent
        self.agent = None
        if enable_agent:
            try:
                # 初始化工具
                tools = [
                    VectorSearchTool(retrieval_client),
                    CalculatorTool(),
                    WebSearchTool(),
                    SQLQueryTool(llm_client=llm_client),
                    CodeInterpreterTool(),
                ]

                # 如果启用了图谱，添加图谱查询工具
                if enable_graph and self.advanced_rag.graph_store:
                    tools.append(GraphQueryTool(self.advanced_rag.graph_store))

                # 初始化 Agent
                self.agent = ReactAgent(
                    llm_client=llm_client, tools=tools, max_iterations=agent_max_iterations
                )
                logger.info(f"Agentic RAG enabled with {len(tools)} tools")
            except Exception as e:
                logger.warning(f"Failed to initialize Agent: {e}")
                self.enable_agent = False

        logger.info(
            f"Ultimate RAG Service initialized:\n"
            f"  Iter 1: hybrid={enable_hybrid}, rerank={enable_rerank}, cache={enable_cache}\n"
            f"  Iter 2: graph={enable_graph}, decomposition={enable_decomposition}\n"
            f"  Iter 3: self_rag={self.enable_self_rag}, compression={self.enable_compression}\n"
            f"  Iter 4: agent={self.enable_agent}"
        )

    async def query(
        self,
        query: str,
        tenant_id: str = "default",
        top_k: int = 5,
        mode: str = "ultimate",
        temperature: float = 0.7,
        # 功能开关
        use_graph: bool = True,
        use_decomposition: bool = True,
        use_self_rag: bool = True,
        use_compression: bool = True,
        use_agent: bool = False,  # 默认关闭，需要显式启用
        compression_ratio: float | None = None,
    ) -> dict[str, Any]:
        """
        终极 RAG 查询

        Args:
            query: 用户查询
            tenant_id: 租户 ID
            top_k: 返回文档数
            mode: 查询模式
            temperature: LLM 温度
            use_graph: 使用图谱检索
            use_decomposition: 使用查询分解
            use_self_rag: 使用自我纠错
            use_compression: 使用上下文压缩
            use_agent: 使用 Agentic RAG（工具调用+多步推理）
            compression_ratio: 压缩比例（覆盖默认值）

        Returns:
            查询结果
        """
        with RAGMetrics(mode=mode, tenant_id=tenant_id):
            try:
                logger.info(f"Ultimate RAG query: {query[:100]}...")

                # Iter 4: Agentic RAG 路径（如果启用且需要）
                if use_agent and self.enable_agent and self.agent and self._should_use_agent(query):
                    logger.info("Using Agentic RAG (ReAct + Tools)")
                    return await self._agentic_query(query, tenant_id)

                # Step 1: 高级检索（包含 Iter 1 + Iter 2）
                logger.info("Step 1: Advanced retrieval (Iter 1 + Iter 2)")
                retrieval_result = await self.advanced_rag.query(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=top_k,
                    mode=mode,
                    temperature=temperature,
                    use_graph=use_graph and self.advanced_rag.enable_graph,
                    use_decomposition=use_decomposition and self.advanced_rag.enable_decomposition,
                )

                # 如果使用了查询分解，已经有最终答案，直接返回
                if retrieval_result.get("strategy") == "query_decomposition":
                    logger.info("Query decomposition used, returning merged answer")
                    return retrieval_result

                # 提取检索结果
                documents = retrieval_result.get("documents", [])
                strategy = retrieval_result.get("strategy", "base")

                logger.info(f"Retrieved {len(documents)} documents using strategy: {strategy}")

                # Step 2: 上下文压缩（Iter 3）
                if use_compression and self.enable_compression:
                    logger.info("Step 2: Context compression (Iter 3)")
                    ratio = compression_ratio or self.compression_ratio
                    compressed_docs = self.compressor.compress_documents(
                        documents=documents, query=query, compression_ratio=ratio
                    )
                    context = self._build_context_from_compressed(compressed_docs)
                    compression_info = {
                        "enabled": True,
                        "ratio": ratio,
                        "tokens_saved": sum(
                            doc.get("compression_info", {}).get("tokens_saved", 0)
                            for doc in compressed_docs
                        ),
                    }
                else:
                    logger.info("Step 2: Building context (no compression)")
                    context = self.base_rag._build_context(documents)
                    compression_info = {"enabled": False}

                # Step 3: 自我纠错生成（Iter 3）
                if use_self_rag and self.enable_self_rag:
                    logger.info("Step 3: Self-RAG generation (Iter 3)")
                    self_rag_result = await self.self_rag.generate_with_self_check(
                        query=query,
                        context=context,
                        temperature=temperature,
                        tenant_id=tenant_id,
                    )

                    answer = self_rag_result["answer"]
                    self_rag_info = {
                        "enabled": True,
                        "has_hallucination": self_rag_result.get("has_hallucination", False),
                        "confidence": self_rag_result.get("confidence", 0.5),
                        "attempts": self_rag_result.get("attempts", 1),
                    }
                else:
                    logger.info("Step 3: Standard generation (no self-check)")
                    answer = await self.base_rag._generate_answer(query, context, temperature)
                    self_rag_info = {"enabled": False}

                # Step 4: 缓存结果
                if self.base_rag.enable_cache and self.base_rag.cache_service:
                    sources = self.base_rag._extract_sources(documents)
                    await self.base_rag.cache_service.set_cached_answer(
                        query, answer, sources=sources
                    )

                # 返回完整结果
                return {
                    "answer": answer,
                    "documents": documents,
                    "sources": self.base_rag._extract_sources(documents),
                    "strategy": strategy,
                    "compression": compression_info,
                    "self_rag": self_rag_info,
                    "features_used": {
                        "hybrid_retrieval": self.base_rag.enable_hybrid,
                        "reranking": self.base_rag.enable_rerank,
                        "semantic_cache": self.base_rag.enable_cache,
                        "graph_rag": use_graph and self.advanced_rag.enable_graph,
                        "query_decomposition": use_decomposition
                        and self.advanced_rag.enable_decomposition,
                        "self_rag": use_self_rag and self.enable_self_rag,
                        "compression": use_compression and self.enable_compression,
                    },
                }

            except Exception as e:
                logger.error(f"Ultimate RAG query failed: {e}", exc_info=True)
                raise

    def _build_context_from_compressed(self, compressed_docs: list[dict]) -> str:
        """从压缩文档构建上下文"""
        context_parts = []
        for i, doc in enumerate(compressed_docs, 1):
            content = doc.get("content", "")
            score = doc.get("rerank_score") or doc.get("rrf_score") or doc.get("score", 0)

            # 添加压缩信息
            compression_info = doc.get("compression_info", {})
            if compression_info:
                ratio = compression_info.get("compression_ratio", 1.0)
                context_parts.append(
                    f"[文档{i}] (相关度: {score:.3f}, 压缩率: {ratio:.2f})\n{content}"
                )
            else:
                context_parts.append(f"[文档{i}] (相关度: {score:.3f})\n{content}")

        return "\n\n".join(context_parts)

    def _should_use_agent(self, query: str) -> bool:
        """
        判断是否应该使用 Agentic RAG

        Args:
            query: 用户查询

        Returns:
            是否使用 Agent
        """
        query_lower = query.lower()

        # 规则：包含计算、实时、代码、数据查询等关键词
        calculation_keywords = ["计算", "增长率", "百分比", "总和", "平均", "占比", "差值"]
        realtime_keywords = ["今天", "现在", "最新", "实时", "当前"]
        data_keywords = ["找出", "查询", "统计", "列出", "排序", "筛选"]
        code_keywords = ["代码", "执行", "运行", "python", "script"]

        # 检查是否包含关键词
        for keyword in calculation_keywords + realtime_keywords + data_keywords + code_keywords:
            if keyword in query_lower:
                logger.info(f"Should use agent: detected keyword '{keyword}'")
                return True

        # 检查是否为多步骤复杂查询（包含"然后"、"接着"、"之后"等连接词）
        multi_step_keywords = ["然后", "接着", "之后", "并且", "以及", "同时"]
        if any(kw in query for kw in multi_step_keywords):
            logger.info("Should use agent: detected multi-step query")
            return True

        return False

    async def _agentic_query(self, query: str, tenant_id: str) -> dict[str, Any]:
        """
        执行 Agentic RAG 查询

        Args:
            query: 用户查询
            tenant_id: 租户 ID

        Returns:
            查询结果
        """
        with AgentMetrics(tenant_id=tenant_id):
            # 使用 Agent 解决问题
            result = await self.agent.solve(query)

            if result.success:
                return {
                    "answer": result.answer,
                    "documents": [],  # Agent 自己获取信息
                    "sources": self._extract_sources_from_agent_steps(result.steps),
                    "strategy": "agentic_rag",
                    "agent_info": {
                        "iterations": result.total_iterations,
                        "tools_used": self._extract_tools_used(result.steps),
                        "success": True,
                    },
                    "features_used": {
                        "agentic_rag": True,
                        "hybrid_retrieval": False,
                        "reranking": False,
                        "semantic_cache": False,
                        "graph_rag": False,
                        "query_decomposition": False,
                        "self_rag": False,
                        "compression": False,
                    },
                }
            else:
                # Agent 失败，降级到标准 RAG
                logger.warning(f"Agent failed: {result.error}, falling back to standard RAG")
                return await self.query(
                    query=query,
                    tenant_id=tenant_id,
                    mode="ultimate",
                    use_agent=False,  # 避免递归
                )

    def _extract_sources_from_agent_steps(self, steps: list) -> list[dict]:
        """从 Agent 步骤中提取信息来源"""
        sources = []
        for step in steps:
            if step.action and step.observation:
                sources.append(
                    {
                        "type": "tool",
                        "tool": step.action.tool_name,
                        "observation": step.observation[:200],  # 截断
                    }
                )
        return sources

    def _extract_tools_used(self, steps: list) -> list[str]:
        """提取使用的工具列表"""
        tools = []
        for step in steps:
            if step.action and step.action.tool_name not in tools:
                tools.append(step.action.tool_name)
        return tools

    async def get_service_status(self) -> dict[str, Any]:
        """获取服务状态"""
        status = {
            "service": "Ultimate RAG v2.1 (with Agentic RAG)",
            "iter1_features": {
                "hybrid_retrieval": self.base_rag.enable_hybrid,
                "reranking": self.base_rag.enable_rerank,
                "semantic_cache": self.base_rag.enable_cache,
            },
            "iter2_features": {
                "graph_rag": self.advanced_rag.enable_graph,
                "query_decomposition": self.advanced_rag.enable_decomposition,
            },
            "iter3_features": {
                "self_rag": self.enable_self_rag,
                "context_compression": self.enable_compression,
            },
            "iter4_features": {
                "agentic_rag": self.enable_agent,
                "tools_count": len(self.agent.tools) if self.agent else 0,
            },
        }

        # 添加缓存统计
        if self.base_rag.enable_cache and self.base_rag.cache_service:
            status["cache_stats"] = self.base_rag.cache_service.get_cache_stats()

        # 添加图谱统计
        if self.advanced_rag.enable_graph:
            try:
                status["graph_stats"] = self.advanced_rag.graph_store.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get graph stats: {e}")

        return status


# 全局实例
_ultimate_rag_service: UltimateRAGService | None = None


def get_ultimate_rag_service(
    retrieval_client,
    llm_client,
    enable_hybrid: bool = True,
    enable_rerank: bool = True,
    enable_cache: bool = True,
    enable_graph: bool = True,
    enable_decomposition: bool = True,
    enable_self_rag: bool = True,
    enable_compression: bool = True,
    enable_agent: bool = True,
    graph_backend: str = "networkx",
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
    compression_ratio: float = 0.5,
    use_llmlingua: bool = False,
    agent_max_iterations: int = 10,
) -> UltimateRAGService:
    """
    获取终极 RAG 服务实例

    Args:
        retrieval_client: 向量检索客户端
        llm_client: LLM 客户端
        enable_hybrid: 启用混合检索
        enable_rerank: 启用重排
        enable_cache: 启用语义缓存
        enable_graph: 启用图谱检索
        enable_decomposition: 启用查询分解
        enable_self_rag: 启用自我纠错
        enable_compression: 启用上下文压缩
        graph_backend: 图谱后端
        neo4j_uri: Neo4j URI
        neo4j_user: Neo4j 用户名
        neo4j_password: Neo4j 密码
        compression_ratio: 压缩比例
        use_llmlingua: 使用 LLMLingua

    Returns:
        UltimateRAGService 实例
    """
    global _ultimate_rag_service

    if _ultimate_rag_service is None:
        _ultimate_rag_service = UltimateRAGService(
            retrieval_client=retrieval_client,
            llm_client=llm_client,
            enable_hybrid=enable_hybrid,
            enable_rerank=enable_rerank,
            enable_cache=enable_cache,
            enable_graph=enable_graph,
            enable_decomposition=enable_decomposition,
            graph_backend=graph_backend,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            enable_self_rag=enable_self_rag,
            enable_compression=enable_compression,
            compression_ratio=compression_ratio,
            use_llmlingua=use_llmlingua,
            enable_agent=enable_agent,
            agent_max_iterations=agent_max_iterations,
        )

    return _ultimate_rag_service
