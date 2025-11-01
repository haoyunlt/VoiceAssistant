"""
Smart Query Enhancement Router - 智能查询增强路由

功能:
- 基于查询复杂度智能路由
- Simple: 仅synonym expansion (无LLM)
- Medium: Multi-Query (template模式)
- Complex: HyDE + Multi-Query (LLM)

目标:
- LLM调用减少≥50%
- 成本节省≥30%
- 质量NDCG@10下降≤2%
"""

import asyncio

from app.observability.logging import logger
from app.services.query.correction_service import QueryCorrectionService
from app.services.query.expansion_service import QueryExpansionService
from app.services.query.hyde_service import HyDEService
from app.services.query.intent_classifier import IntentClassifier, QueryComplexity
from app.services.query.multi_query_service import MultiQueryService
from app.services.query.rewriting_service import QueryRewritingService


class SmartQueryRouter:
    """智能查询增强路由"""

    def __init__(
        self,
        llm_endpoint: str | None = None,
        enable_llm_for_complex: bool = True,
        cost_budget: float | None = None,
    ):
        """
        初始化智能路由器

        Args:
            llm_endpoint: LLM端点
            enable_llm_for_complex: 复杂查询是否启用LLM
            cost_budget: 成本预算（美元/请求）
        """
        self.llm_endpoint = llm_endpoint
        self.enable_llm_for_complex = enable_llm_for_complex
        self.cost_budget = cost_budget

        # 初始化服务
        self.intent_classifier = IntentClassifier()
        self.correction_service = QueryCorrectionService()
        self.rewriting_service = QueryRewritingService(
            llm_endpoint=llm_endpoint,
            enable_llm=False,  # 默认关闭LLM
        )
        self.expansion_service = QueryExpansionService(methods=["synonym"])
        self.multi_query_service = MultiQueryService(llm_endpoint=llm_endpoint, enable_llm=False)
        self.hyde_service = HyDEService(llm_endpoint=llm_endpoint)

        logger.info(
            f"Smart query router initialized: "
            f"llm_enabled={enable_llm_for_complex}, cost_budget={cost_budget}"
        )

    async def enhance_query(self, query: str) -> dict[str, any]:
        """
        智能增强查询

        Args:
            query: 原始查询

        Returns:
            增强结果字典
        """
        # 1. 评估复杂度
        complexity = await self._evaluate_complexity(query)

        # 2. 根据复杂度选择策略
        if complexity == QueryComplexity.SIMPLE:
            enhanced = await self._simple_strategy(query)
        elif complexity == QueryComplexity.MEDIUM:
            enhanced = await self._medium_strategy(query)
        elif complexity == QueryComplexity.COMPLEX:
            enhanced = await self._complex_strategy(query)
        else:
            enhanced = await self._knowledge_intensive_strategy(query)

        enhanced["complexity"] = complexity.value
        enhanced["original_query"] = query

        logger.info(
            f"Query enhanced: complexity={complexity.value}, "
            f"strategies={enhanced.get('strategies', [])}, "
            f"llm_used={enhanced.get('llm_used', False)}"
        )

        return enhanced

    async def _evaluate_complexity(self, query: str) -> QueryComplexity:
        """评估查询复杂度"""
        query_length = len(query)
        word_count = len(query.split())

        # 简单查询
        if query_length < 10 and word_count <= 3:
            return QueryComplexity.SIMPLE

        # 知识密集型
        knowledge_patterns = ["什么是", "解释", "原理", "机制", "为什么"]
        if any(pattern in query for pattern in knowledge_patterns):
            return QueryComplexity.KNOWLEDGE_INTENSIVE

        # 复杂查询
        complex_patterns = ["比较", "对比", "区别", "优缺点"]
        if any(pattern in query for pattern in complex_patterns) or word_count > 15:
            return QueryComplexity.COMPLEX

        # 默认中等
        return QueryComplexity.MEDIUM

    async def _simple_strategy(self, query: str) -> dict:
        """简单查询策略: 仅纠错 + Synonym扩展"""
        # 1. 纠错
        corrected = await self.correction_service.correct(query)

        # 2. Synonym扩展
        expanded = await self.expansion_service.expand(corrected.corrected_query, enable_llm=False)

        return {
            "queries": expanded.expanded[:3],
            "strategies": ["correction", "synonym_expansion"],
            "llm_used": False,
            "estimated_cost": 0.0,
        }

    async def _medium_strategy(self, query: str) -> dict:
        """中等查询策略: 纠错 + 重写 + Multi-Query(template)"""
        # 1. 纠错
        corrected = await self.correction_service.correct(query)

        # 2. 重写
        rewritten = await self.rewriting_service.rewrite(corrected.corrected_query)

        # 3. Multi-Query (template模式)
        multi = await self.multi_query_service.generate(corrected.corrected_query, enable_llm=False)

        # 合并queries
        all_queries = [corrected.corrected_query] + rewritten.rewritten_queries + multi.queries
        unique_queries = list(dict.fromkeys(all_queries))[:5]

        return {
            "queries": unique_queries,
            "strategies": ["correction", "rewriting", "multi_query_template"],
            "llm_used": False,
            "estimated_cost": 0.0,
        }

    async def _complex_strategy(self, query: str) -> dict:
        """复杂查询策略: 完整增强 + 可选LLM"""
        # 1. 纠错
        corrected = await self.correction_service.correct(query)

        # 2. 重写 (可选LLM)
        use_llm = self.enable_llm_for_complex and self.llm_endpoint
        rewritten = await self.rewriting_service.rewrite(corrected.corrected_query)

        # 3. Multi-Query (可选LLM)
        multi = await self.multi_query_service.generate(
            corrected.corrected_query, enable_llm=use_llm
        )

        # 合并queries
        all_queries = [corrected.corrected_query] + rewritten.rewritten_queries + multi.queries
        unique_queries = list(dict.fromkeys(all_queries))[:7]

        return {
            "queries": unique_queries,
            "strategies": [
                "correction",
                "rewriting",
                "multi_query_llm" if use_llm else "multi_query_template",
            ],
            "llm_used": use_llm,
            "estimated_cost": 0.0002 if use_llm else 0.0,
        }

    async def _knowledge_intensive_strategy(self, query: str) -> dict:
        """知识密集型策略: HyDE + Multi-Query"""
        use_llm = self.enable_llm_for_complex and self.llm_endpoint

        # 1. HyDE
        hyde_result = await self.hyde_service.generate(query)

        # 2. Multi-Query
        multi = await self.multi_query_service.generate(query, enable_llm=use_llm)

        # 使用HyDE文档作为主查询
        all_queries = [hyde_result.hypothetical_document] + multi.queries
        unique_queries = list(dict.fromkeys(all_queries))[:5]

        return {
            "queries": unique_queries,
            "strategies": [
                "hyde",
                "multi_query_llm" if use_llm else "multi_query_template",
            ],
            "llm_used": use_llm,
            "estimated_cost": 0.0005 if use_llm else 0.0,
        }

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "llm_endpoint": self.llm_endpoint,
            "enable_llm_for_complex": self.enable_llm_for_complex,
            "cost_budget": self.cost_budget,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        router = SmartQueryRouter(enable_llm_for_complex=False)

        test_queries = [
            "Python",  # Simple
            "如何使用Docker部署应用",  # Medium
            "Python和Java在Web开发中的优缺点对比",  # Complex
            "什么是量子计算的基本原理",  # Knowledge-intensive
        ]

        for query in test_queries:
            result = await router.enhance_query(query)
            print(f"\n原查询: {query}")
            print(f"复杂度: {result['complexity']}")
            print(f"增强查询: {result['queries']}")
            print(f"策略: {result['strategies']}")
            print(f"LLM使用: {result['llm_used']}")

    asyncio.run(test())
