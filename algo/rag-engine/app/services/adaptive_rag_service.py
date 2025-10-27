"""Adaptive RAG服务 - 根据查询类型自适应选择检索策略"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """查询类型"""
    SIMPLE_FACT = "simple_fact"  # 简单事实查询
    COMPLEX_REASONING = "complex_reasoning"  # 复杂推理查询
    MULTI_HOP = "multi_hop"  # 多跳查询
    COMPARISON = "comparison"  # 对比查询
    AGGREGATION = "aggregation"  # 聚合查询
    OPEN_ENDED = "open_ended"  # 开放式查询


class RetrievalStrategy(Enum):
    """检索策略"""
    DIRECT = "direct"  # 直接检索
    HYDE = "hyde"  # HyDE检索
    QUERY_DECOMPOSITION = "query_decomposition"  # 查询分解
    ITERATIVE = "iterative"  # 迭代检索
    HYBRID = "hybrid"  # 混合检索


class AdaptiveRAGService:
    """
    Adaptive RAG服务
    
    根据查询特征自动选择最佳检索和生成策略：
    1. 查询分析：判断查询类型和复杂度
    2. 策略选择：基于分析结果选择检索策略
    3. 动态调整：根据中间结果调整策略参数
    4. 性能优化：记录策略效果用于未来优化
    """

    def __init__(
        self,
        llm_client,
        retrieval_client,
        embedding_client
    ):
        """
        初始化Adaptive RAG服务
        
        Args:
            llm_client: LLM客户端
            retrieval_client: 检索客户端
            embedding_client: 向量化客户端
        """
        self.llm_client = llm_client
        self.retrieval_client = retrieval_client
        self.embedding_client = embedding_client
        
        # 策略性能记录
        self.strategy_performance: Dict[str, Dict] = {}

    async def query(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str] = None,
        user_preferences: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        自适应RAG查询
        
        Args:
            query: 用户查询
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            user_preferences: 用户偏好设置
            
        Returns:
            查询结果
        """
        logger.info(f"Adaptive RAG query: {query}")
        
        # 1. 分析查询
        query_analysis = await self._analyze_query(query)
        
        logger.info(f"Query type: {query_analysis['type']}, complexity: {query_analysis['complexity']}")
        
        # 2. 选择策略
        strategy = self._select_strategy(query_analysis, user_preferences)
        
        logger.info(f"Selected strategy: {strategy}")
        
        # 3. 执行检索和生成
        result = await self._execute_strategy(
            strategy=strategy,
            query=query,
            query_analysis=query_analysis,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id
        )
        
        # 4. 记录性能
        self._record_performance(strategy, result)
        
        return {
            "answer": result["answer"],
            "query_type": query_analysis["type"],
            "complexity": query_analysis["complexity"],
            "strategy_used": strategy.value,
            "retrieval_count": result.get("retrieval_count", 0),
            "documents": result.get("documents", []),
            "confidence": result.get("confidence", 0.0),
            "metadata": {
                "query_analysis": query_analysis,
                "execution_time": result.get("execution_time", 0)
            }
        }

    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        分析查询特征
        
        Returns:
            查询分析结果
        """
        import json
        
        prompt = f"""Analyze the following query and classify it.

Query: {query}

Provide analysis in JSON format:
{{
    "type": "simple_fact|complex_reasoning|multi_hop|comparison|aggregation|open_ended",
    "complexity": 1-10,
    "requires_multiple_sources": true/false,
    "temporal_aspect": true/false,
    "requires_calculation": true/false,
    "key_concepts": ["concept1", "concept2", ...],
    "reasoning": "brief explanation"
}}
"""
        
        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=300
        )
        
        try:
            analysis = json.loads(response)
            return analysis
        except json.JSONDecodeError:
            # 默认分析
            return {
                "type": "simple_fact",
                "complexity": 5,
                "requires_multiple_sources": False,
                "temporal_aspect": False,
                "requires_calculation": False,
                "key_concepts": [],
                "reasoning": "Failed to parse analysis"
            }

    def _select_strategy(
        self,
        query_analysis: Dict[str, Any],
        user_preferences: Optional[Dict] = None
    ) -> RetrievalStrategy:
        """
        根据查询分析选择检索策略
        
        Args:
            query_analysis: 查询分析结果
            user_preferences: 用户偏好
            
        Returns:
            选择的检索策略
        """
        query_type = query_analysis.get("type", "simple_fact")
        complexity = query_analysis.get("complexity", 5)
        requires_multiple = query_analysis.get("requires_multiple_sources", False)
        
        # 用户偏好
        prefer_accuracy = user_preferences and user_preferences.get("prefer_accuracy", False)
        prefer_speed = user_preferences and user_preferences.get("prefer_speed", False)
        
        # 策略选择逻辑
        if prefer_speed and complexity <= 3:
            return RetrievalStrategy.DIRECT
        
        if query_type == "multi_hop" or requires_multiple:
            return RetrievalStrategy.ITERATIVE
        
        if query_type == "complex_reasoning" and complexity >= 7:
            return RetrievalStrategy.QUERY_DECOMPOSITION
        
        if query_type == "comparison" or query_type == "aggregation":
            return RetrievalStrategy.HYBRID
        
        if prefer_accuracy or complexity >= 6:
            return RetrievalStrategy.HYDE
        
        return RetrievalStrategy.DIRECT

    async def _execute_strategy(
        self,
        strategy: RetrievalStrategy,
        query: str,
        query_analysis: Dict[str, Any],
        tenant_id: str,
        knowledge_base_id: Optional[str]
    ) -> Dict[str, Any]:
        """执行选定的策略"""
        import time
        start_time = time.time()
        
        if strategy == RetrievalStrategy.DIRECT:
            result = await self._direct_retrieval(query, tenant_id, knowledge_base_id)
        elif strategy == RetrievalStrategy.HYDE:
            result = await self._hyde_retrieval(query, tenant_id, knowledge_base_id)
        elif strategy == RetrievalStrategy.QUERY_DECOMPOSITION:
            result = await self._decomposition_retrieval(query, query_analysis, tenant_id, knowledge_base_id)
        elif strategy == RetrievalStrategy.ITERATIVE:
            result = await self._iterative_retrieval(query, tenant_id, knowledge_base_id)
        elif strategy == RetrievalStrategy.HYBRID:
            result = await self._hybrid_retrieval(query, tenant_id, knowledge_base_id)
        else:
            result = await self._direct_retrieval(query, tenant_id, knowledge_base_id)
        
        execution_time = time.time() - start_time
        result["execution_time"] = execution_time
        
        return result

    async def _direct_retrieval(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str]
    ) -> Dict[str, Any]:
        """直接检索策略"""
        # 简单的向量检索
        documents = await self.retrieval_client.vector_search(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=5
        )
        
        # 生成答案
        answer = await self._generate_answer(query, documents)
        
        return {
            "answer": answer,
            "documents": documents,
            "retrieval_count": 1,
            "confidence": self._estimate_confidence(documents)
        }

    async def _hyde_retrieval(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str]
    ) -> Dict[str, Any]:
        """HyDE检索策略"""
        # 生成假设文档
        hypothetical_doc = await self._generate_hypothetical_document(query)
        
        # 使用假设文档的向量检索
        doc_embedding = await self.embedding_client.embed_text(hypothetical_doc)
        
        documents = await self.retrieval_client.vector_search_by_embedding(
            embedding=doc_embedding,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=5
        )
        
        # 生成答案
        answer = await self._generate_answer(query, documents)
        
        return {
            "answer": answer,
            "documents": documents,
            "retrieval_count": 1,
            "hypothetical_doc": hypothetical_doc,
            "confidence": self._estimate_confidence(documents)
        }

    async def _decomposition_retrieval(
        self,
        query: str,
        query_analysis: Dict[str, Any],
        tenant_id: str,
        knowledge_base_id: Optional[str]
    ) -> Dict[str, Any]:
        """查询分解策略"""
        # 分解查询为子查询
        sub_queries = await self._decompose_query(query, query_analysis)
        
        # 对每个子查询检索
        all_documents = []
        for sub_query in sub_queries:
            docs = await self.retrieval_client.vector_search(
                query=sub_query,
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                top_k=3
            )
            all_documents.extend(docs)
        
        # 去重
        unique_docs = self._deduplicate_documents(all_documents)
        
        # 生成综合答案
        answer = await self._generate_answer(query, unique_docs)
        
        return {
            "answer": answer,
            "documents": unique_docs,
            "retrieval_count": len(sub_queries),
            "sub_queries": sub_queries,
            "confidence": self._estimate_confidence(unique_docs)
        }

    async def _iterative_retrieval(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str],
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """迭代检索策略"""
        all_documents = []
        current_query = query
        
        for i in range(max_iterations):
            # 检索
            docs = await self.retrieval_client.vector_search(
                query=current_query,
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                top_k=5
            )
            
            all_documents.extend(docs)
            
            # 判断是否需要继续
            if i < max_iterations - 1:
                need_more, next_query = await self._check_need_more_retrieval(
                    query, docs
                )
                
                if not need_more:
                    break
                
                current_query = next_query
        
        # 去重
        unique_docs = self._deduplicate_documents(all_documents)
        
        # 生成答案
        answer = await self._generate_answer(query, unique_docs)
        
        return {
            "answer": answer,
            "documents": unique_docs,
            "retrieval_count": i + 1,
            "confidence": self._estimate_confidence(unique_docs)
        }

    async def _hybrid_retrieval(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str]
    ) -> Dict[str, Any]:
        """混合检索策略"""
        # 向量检索 + BM25检索
        documents = await self.retrieval_client.hybrid_search(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=10
        )
        
        # 重排序
        reranked_docs = await self._rerank_documents(query, documents)
        
        # 生成答案
        answer = await self._generate_answer(query, reranked_docs[:5])
        
        return {
            "answer": answer,
            "documents": reranked_docs[:5],
            "retrieval_count": 1,
            "confidence": self._estimate_confidence(reranked_docs[:5])
        }

    async def _generate_hypothetical_document(self, query: str) -> str:
        """生成假设文档（用于HyDE）"""
        prompt = f"""Given the question, write a detailed answer as it would appear in a knowledge base.

Question: {query}

Detailed Answer:"""
        
        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=400
        )
        
        return response.strip()

    async def _decompose_query(
        self,
        query: str,
        query_analysis: Dict[str, Any]
    ) -> List[str]:
        """分解查询为子查询"""
        import json
        
        prompt = f"""Decompose the following complex query into simpler sub-queries.

Query: {query}
Key Concepts: {', '.join(query_analysis.get('key_concepts', []))}

Provide 2-4 sub-queries in JSON format:
["sub-query 1", "sub-query 2", ...]
"""
        
        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=200
        )
        
        try:
            sub_queries = json.loads(response)
            return sub_queries
        except json.JSONDecodeError:
            return [query]

    async def _check_need_more_retrieval(
        self,
        query: str,
        documents: List[Dict]
    ) -> tuple[bool, str]:
        """检查是否需要更多检索"""
        import json
        
        docs_summary = "\n".join([
            f"- {doc.get('content', '')[:100]}"
            for doc in documents[:3]
        ])
        
        prompt = f"""Based on the query and retrieved documents, determine if more information is needed.

Query: {query}

Retrieved Documents:
{docs_summary}

Respond in JSON:
{{
    "need_more": true/false,
    "next_query": "reformulated query if need_more is true"
}}
"""
        
        response = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=150
        )
        
        try:
            result = json.loads(response)
            return result.get("need_more", False), result.get("next_query", query)
        except json.JSONDecodeError:
            return False, query

    async def _generate_answer(
        self,
        query: str,
        documents: List[Dict]
    ) -> str:
        """基于文档生成答案"""
        if not documents:
            return "抱歉，没有找到相关信息。"
        
        context = "\n\n".join([
            f"[文档{i+1}]: {doc.get('content', '')}"
            for i, doc in enumerate(documents[:5])
        ])
        
        prompt = f"""Based on the following documents, answer the query.

Query: {query}

Documents:
{context}

Answer:"""
        
        answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        return answer.strip()

    async def _rerank_documents(
        self,
        query: str,
        documents: List[Dict]
    ) -> List[Dict]:
        """重排序文档"""
        # 简化实现：使用LLM评分
        scored_docs = []
        
        for doc in documents:
            score = await self._score_document(query, doc)
            scored_docs.append({
                **doc,
                "rerank_score": score
            })
        
        # 按分数排序
        scored_docs.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        return scored_docs

    async def _score_document(self, query: str, document: Dict) -> float:
        """为文档评分"""
        # 简化实现：基于相似度
        return document.get("score", 0.5)

    def _deduplicate_documents(self, documents: List[Dict]) -> List[Dict]:
        """去重文档"""
        seen_ids = set()
        unique_docs = []
        
        for doc in documents:
            doc_id = doc.get("id", doc.get("chunk_id", ""))
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_docs.append(doc)
        
        return unique_docs

    def _estimate_confidence(self, documents: List[Dict]) -> float:
        """估算答案置信度"""
        if not documents:
            return 0.0
        
        # 基于文档分数估算
        avg_score = sum(doc.get("score", 0) for doc in documents) / len(documents)
        return min(avg_score, 1.0)

    def _record_performance(self, strategy: RetrievalStrategy, result: Dict):
        """记录策略性能"""
        strategy_name = strategy.value
        
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {
                "count": 0,
                "total_time": 0,
                "total_confidence": 0
            }
        
        stats = self.strategy_performance[strategy_name]
        stats["count"] += 1
        stats["total_time"] += result.get("execution_time", 0)
        stats["total_confidence"] += result.get("confidence", 0)

    def get_strategy_stats(self) -> Dict[str, Dict]:
        """获取策略统计信息"""
        stats = {}
        
        for strategy_name, data in self.strategy_performance.items():
            if data["count"] > 0:
                stats[strategy_name] = {
                    "count": data["count"],
                    "avg_time": data["total_time"] / data["count"],
                    "avg_confidence": data["total_confidence"] / data["count"]
                }
        
        return stats
