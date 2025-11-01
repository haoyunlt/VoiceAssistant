"""自适应检索服务"""

import re

from pydantic import BaseModel

from app.core.logging import logger


class QueryComplexity(BaseModel):
    """查询复杂度"""

    level: str  # simple, medium, complex
    score: int
    factors: dict


class RetrievedDocument(BaseModel):
    """检索到的文档"""

    chunk_id: str
    content: str
    score: float = 0.0
    metadata: dict = {}


class AdaptiveRetrievalService:
    """自适应检索服务"""

    def __init__(self, retrieval_client, rerank_service, query_expansion_service=None):
        """初始化

        Args:
            retrieval_client: 检索客户端
            rerank_service: 重排序服务
            query_expansion_service: 查询扩展服务（可选）
        """
        self.retrieval_client = retrieval_client
        self.rerank_service = rerank_service
        self.query_expansion_service = query_expansion_service

    async def adaptive_search(
        self, query: str, tenant_id: str, knowledge_base_id: str, max_results: int = 10
    ) -> list[RetrievedDocument]:
        """自适应检索

        根据查询复杂度自动选择检索策略

        Args:
            query: 查询文本
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            max_results: 最大结果数

        Returns:
            检索到的文档列表
        """
        # 1. 分析查询复杂度
        complexity = await self._analyze_query_complexity(query)

        logger.info(f"Query complexity: {complexity.level} (score: {complexity.score})")

        # 2. 根据复杂度选择策略
        if complexity.level == "simple":
            # 简单查询：仅向量检索，top 5
            documents = await self._simple_search(query, tenant_id, knowledge_base_id, top_k=5)

        elif complexity.level == "medium":
            # 中等查询：混合检索，top 10
            documents = await self._medium_search(query, tenant_id, knowledge_base_id, top_k=10)

        else:  # complex
            # 复杂查询：混合检索 + 查询扩展 + 重排序，top 20
            documents = await self._complex_search(query, tenant_id, knowledge_base_id, top_k=20)

        # 3. 返回指定数量的结果
        return documents[:max_results]

    async def _analyze_query_complexity(self, query: str) -> QueryComplexity:
        """分析查询复杂度

        Args:
            query: 查询文本

        Returns:
            查询复杂度
        """
        factors = {}
        score = 0

        # 1. 长度因素
        words = query.split()
        factors["length"] = len(words)
        if len(words) > 20:
            score += 2
        elif len(words) > 10:
            score += 1

        # 2. 数字因素
        has_numbers = bool(re.search(r"\d", query))
        factors["has_numbers"] = has_numbers
        if has_numbers:
            score += 1

        # 3. 比较关键词
        comparison_keywords = [
            "比较",
            "对比",
            "区别",
            "差异",
            "不同",
            "相同",
            "compare",
            "difference",
            "vs",
        ]
        has_comparison = any(keyword in query.lower() for keyword in comparison_keywords)
        factors["has_comparison"] = has_comparison
        if has_comparison:
            score += 2

        # 4. 聚合关键词
        aggregation_keywords = [
            "总结",
            "汇总",
            "统计",
            "分析",
            "概述",
            "summarize",
            "analyze",
            "overview",
        ]
        has_aggregation = any(keyword in query.lower() for keyword in aggregation_keywords)
        factors["has_aggregation"] = has_aggregation
        if has_aggregation:
            score += 3

        # 5. 时间关键词
        temporal_keywords = [
            "最近",
            "最新",
            "历史",
            "过去",
            "未来",
            "recent",
            "latest",
            "history",
            "past",
            "future",
        ]
        has_temporal = any(keyword in query.lower() for keyword in temporal_keywords)
        factors["has_temporal"] = has_temporal
        if has_temporal:
            score += 1

        # 6. 因果关键词
        causal_keywords = [
            "为什么",
            "原因",
            "导致",
            "影响",
            "结果",
            "why",
            "cause",
            "reason",
            "result",
            "impact",
        ]
        has_causal = any(keyword in query.lower() for keyword in causal_keywords)
        factors["has_causal"] = has_causal
        if has_causal:
            score += 2

        # 7. 多个问号
        question_marks = query.count("?") + query.count("？")
        factors["question_marks"] = question_marks
        if question_marks > 1:
            score += 1

        # 判断级别
        if score <= 2:
            level = "simple"
        elif score <= 5:
            level = "medium"
        else:
            level = "complex"

        return QueryComplexity(level=level, score=score, factors=factors)

    async def _simple_search(
        self, query: str, tenant_id: str, knowledge_base_id: str, top_k: int = 5
    ) -> list[RetrievedDocument]:
        """简单检索：仅向量检索

        Args:
            query: 查询文本
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回数量

        Returns:
            检索结果
        """
        documents = await self.retrieval_client.vector_search(
            query=query, tenant_id=tenant_id, knowledge_base_id=knowledge_base_id, top_k=top_k
        )
        return documents

    async def _medium_search(
        self, query: str, tenant_id: str, knowledge_base_id: str, top_k: int = 10
    ) -> list[RetrievedDocument]:
        """中等检索：混合检索

        Args:
            query: 查询文本
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回数量

        Returns:
            检索结果
        """
        documents = await self.retrieval_client.hybrid_search(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            top_k=top_k,
            alpha=0.6,  # 向量权重
        )
        return documents

    async def _complex_search(
        self, query: str, tenant_id: str, knowledge_base_id: str, top_k: int = 20
    ) -> list[RetrievedDocument]:
        """复杂检索：混合检索 + 查询扩展 + 重排序

        Args:
            query: 查询文本
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID
            top_k: 返回数量

        Returns:
            检索结果
        """
        all_docs = []

        # 1. 查询扩展（如果可用）
        if self.query_expansion_service:
            expanded_queries = await self.query_expansion_service.expand_query(
                query, num_expansions=2
            )
        else:
            expanded_queries = [query]

        # 2. 对每个查询执行混合检索
        for q in expanded_queries:
            docs = await self.retrieval_client.hybrid_search(
                query=q,
                tenant_id=tenant_id,
                knowledge_base_id=knowledge_base_id,
                top_k=10,
                alpha=0.5,
            )
            all_docs.extend(docs)

        # 3. 去重
        unique_docs = self._deduplicate(all_docs)

        # 4. 重排序
        reranked_docs = await self.rerank_service.rerank(
            query=query, documents=unique_docs, top_k=top_k
        )

        return reranked_docs

    def _deduplicate(self, documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
        """去重

        Args:
            documents: 文档列表

        Returns:
            去重后的文档列表
        """
        seen = set()
        unique_docs = []

        for doc in documents:
            if doc.chunk_id not in seen:
                seen.add(doc.chunk_id)
                unique_docs.append(doc)

        return unique_docs

    async def get_strategy_explanation(self, query: str) -> dict:
        """获取检索策略说明

        Args:
            query: 查询文本

        Returns:
            策略说明
        """
        complexity = await self._analyze_query_complexity(query)

        strategies = {
            "simple": {
                "name": "简单检索",
                "methods": ["向量检索"],
                "top_k": 5,
                "description": "适用于简单直接的问题，使用向量相似度检索",
            },
            "medium": {
                "name": "混合检索",
                "methods": ["向量检索", "BM25检索", "RRF融合"],
                "top_k": 10,
                "description": "适用于中等复杂度的问题，结合向量和关键词检索",
            },
            "complex": {
                "name": "增强检索",
                "methods": ["查询扩展", "混合检索", "Cross-Encoder重排序"],
                "top_k": 20,
                "description": "适用于复杂问题，使用多种检索策略和重排序",
            },
        }

        strategy = strategies[complexity.level]

        return {"complexity": complexity.dict(), "strategy": strategy}
