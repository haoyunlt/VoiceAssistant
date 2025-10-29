"""
Adaptive Retrieval Strategy - 自适应检索策略

功能:
- 根据查询复杂度动态选择检索策略
- 平衡质量、延迟和成本
- 自动优化检索参数

策略选择:
- Simple Query: 向量检索 (快速)
- Medium Query: 混合检索 (平衡)
- Complex Query: 混合检索 + Multi-Query + Rerank (高质量)
- Knowledge-Intensive: HyDE + 向量检索 (准确)

目标:
- 平均延迟降低≥20%
- 质量保持或提升
- 成本降低≥15%
"""

from dataclasses import dataclass
from enum import Enum

from app.core.logging import logger
from app.models.retrieval import HybridRequest, HybridResponse
from app.services.query.intent_classifier import IntentClassifier, QueryIntent


class QueryComplexity(str, Enum):
    """查询复杂度"""

    SIMPLE = "simple"  # 简单查询
    MEDIUM = "medium"  # 中等复杂度
    COMPLEX = "complex"  # 复杂查询
    KNOWLEDGE_INTENSIVE = "knowledge_intensive"  # 知识密集型


@dataclass
class AdaptiveStrategy:
    """自适应策略配置"""

    complexity: QueryComplexity
    retrieval_method: str  # vector, bm25, hybrid
    enable_query_expansion: bool = False
    enable_multi_query: bool = False
    enable_hyde: bool = False
    enable_rerank: bool = False
    top_k: int = 10
    estimated_latency_ms: float = 0
    estimated_cost: float = 0


class AdaptiveRetrievalService:
    """自适应检索服务"""

    def __init__(self, intent_classifier: IntentClassifier | None = None):
        """
        初始化自适应检索服务

        Args:
            intent_classifier: 意图分类器
        """
        self.intent_classifier = intent_classifier or IntentClassifier()

        logger.info("Adaptive retrieval service initialized")

    async def select_strategy(
        self, query: str, request: HybridRequest | None = None
    ) -> AdaptiveStrategy:
        """
        选择自适应策略

        Args:
            query: 用户查询
            request: 原始请求（可选）

        Returns:
            自适应策略
        """
        # 1. 评估查询复杂度
        complexity = self._evaluate_complexity(query)

        # 2. 获取查询意图
        intent_result = await self.intent_classifier.classify(query)

        # 3. 选择策略
        strategy = self._select_strategy_for_complexity(complexity, intent_result.intent)

        logger.info(
            f"Adaptive strategy selected: complexity={complexity.value}, "
            f"intent={intent_result.intent.value}, "
            f"method={strategy.retrieval_method}"
        )

        return strategy

    def _evaluate_complexity(self, query: str) -> QueryComplexity:
        """
        评估查询复杂度

        策略:
        - 查询长度
        - 子句数量
        - 关键词密度
        - 特殊模式

        Args:
            query: 用户查询

        Returns:
            查询复杂度
        """
        query_length = len(query)
        word_count = len(query.split())

        # 简单规则判断
        if query_length < 10 and word_count <= 3:
            return QueryComplexity.SIMPLE

        # 知识密集型判断
        knowledge_patterns = ["什么是", "解释", "原理", "机制", "为什么"]
        if any(pattern in query for pattern in knowledge_patterns):
            return QueryComplexity.KNOWLEDGE_INTENSIVE

        # 复杂查询判断
        complex_patterns = ["比较", "对比", "区别", "优缺点", "和.*的关系"]
        if any(pattern in query for pattern in complex_patterns) or word_count > 15:
            return QueryComplexity.COMPLEX

        # 默认中等复杂度
        return QueryComplexity.MEDIUM

    def _select_strategy_for_complexity(
        self, complexity: QueryComplexity, intent: QueryIntent
    ) -> AdaptiveStrategy:
        """
        根据复杂度选择策略

        Args:
            complexity: 查询复杂度
            intent: 查询意图

        Returns:
            自适应策略
        """
        if complexity == QueryComplexity.SIMPLE:
            # 简单查询：向量检索 + 可选rerank
            return AdaptiveStrategy(
                complexity=complexity,
                retrieval_method="vector",
                enable_query_expansion=False,
                enable_multi_query=False,
                enable_hyde=False,
                enable_rerank=False,
                top_k=5,
                estimated_latency_ms=50,
                estimated_cost=0.0001,
            )

        elif complexity == QueryComplexity.MEDIUM:
            # 中等查询：混合检索
            return AdaptiveStrategy(
                complexity=complexity,
                retrieval_method="hybrid",
                enable_query_expansion=True,
                enable_multi_query=False,
                enable_hyde=False,
                enable_rerank=True,
                top_k=10,
                estimated_latency_ms=150,
                estimated_cost=0.0002,
            )

        elif complexity == QueryComplexity.COMPLEX:
            # 复杂查询：混合检索 + Multi-Query + Rerank
            return AdaptiveStrategy(
                complexity=complexity,
                retrieval_method="hybrid",
                enable_query_expansion=True,
                enable_multi_query=True,
                enable_hyde=False,
                enable_rerank=True,
                top_k=20,
                estimated_latency_ms=300,
                estimated_cost=0.0005,
            )

        elif complexity == QueryComplexity.KNOWLEDGE_INTENSIVE:
            # 知识密集型：HyDE + 向量检索 + Rerank
            return AdaptiveStrategy(
                complexity=complexity,
                retrieval_method="vector",
                enable_query_expansion=False,
                enable_multi_query=False,
                enable_hyde=True,
                enable_rerank=True,
                top_k=10,
                estimated_latency_ms=600,  # HyDE需要LLM调用
                estimated_cost=0.001,
            )

        # 默认策略
        return AdaptiveStrategy(
            complexity=complexity,
            retrieval_method="hybrid",
            enable_query_expansion=False,
            enable_multi_query=False,
            enable_hyde=False,
            enable_rerank=False,
            top_k=10,
            estimated_latency_ms=100,
            estimated_cost=0.0001,
        )

    async def adaptive_search(
        self, query: str, base_request: HybridRequest | None = None
    ) -> tuple[HybridResponse, AdaptiveStrategy]:
        """
        自适应检索

        Args:
            query: 用户查询
            base_request: 基础请求（可选）

        Returns:
            (检索结果, 使用的策略)
        """
        # 选择策略
        strategy = await self.select_strategy(query, base_request)

        # 构建请求
        HybridRequest(
            query=query,
            top_k=strategy.top_k,
            enable_query_expansion=strategy.enable_query_expansion,
            enable_multi_query=strategy.enable_multi_query,
            enable_rerank=strategy.enable_rerank,
        )

        # 这里应该调用实际的retrieval_service
        # 为了示例，返回模拟结果
        response = HybridResponse(
            documents=[],
            query=query,
            vector_count=0,
            bm25_count=0,
            reranked=strategy.enable_rerank,
            latency_ms=strategy.estimated_latency_ms,
        )

        return response, strategy

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "intent_classifier": "enabled",
            "complexity_levels": len(QueryComplexity),
        }


# 使用示例
if __name__ == "__main__":
    import asyncio

    async def test():
        service = AdaptiveRetrievalService()

        test_queries = [
            "Python",  # Simple
            "如何使用Python进行数据分析",  # Medium
            "Python和Java在Web开发中的优缺点对比",  # Complex
            "什么是量子计算的基本原理",  # Knowledge-intensive
        ]

        for query in test_queries:
            strategy = await service.select_strategy(query)
            print(f"\n查询: {query}")
            print(f"  复杂度: {strategy.complexity.value}")
            print(f"  检索方法: {strategy.retrieval_method}")
            print(f"  Query Expansion: {strategy.enable_query_expansion}")
            print(f"  Multi-Query: {strategy.enable_multi_query}")
            print(f"  HyDE: {strategy.enable_hyde}")
            print(f"  Rerank: {strategy.enable_rerank}")
            print(f"  预估延迟: {strategy.estimated_latency_ms}ms")

    asyncio.run(test())
