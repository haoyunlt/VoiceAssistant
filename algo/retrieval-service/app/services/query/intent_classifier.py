"""
Query Intent Classification Service - 查询意图分类服务

功能:
- 识别查询的意图类型
- 根据意图选择最优检索策略
- 提升检索效率和准确性

意图类型:
- factual: 事实性查询 ("什么是XXX")  → 向量检索优先
- howto: 操作指南 ("如何XXX")  → 混合检索 + 结构化
- troubleshooting: 故障排除 ("为什么XXX失败")  → 关键词检索优先
- comparison: 对比分析 ("XXX和YYY的区别")  → 多文档检索
- conceptual: 概念理解 ("解释XXX")  → 向量检索 + HyDE
- openended: 开放式问题  → Multi-Query + 混合检索

分类方法:
1. 规则based (快速，延迟<1ms)
2. ML模型 (准确，延迟<30ms) - 可选
"""

import re
import time
from dataclasses import dataclass
from enum import Enum


class QueryIntent(str, Enum):
    """查询意图枚举"""

    FACTUAL = "factual"  # 事实性查询
    HOWTO = "howto"  # 操作指南
    TROUBLESHOOTING = "troubleshooting"  # 故障排除
    COMPARISON = "comparison"  # 对比分析
    CONCEPTUAL = "conceptual"  # 概念理解
    OPENENDED = "openended"  # 开放式问题
    UNKNOWN = "unknown"  # 未知类型


@dataclass
class IntentResult:
    """意图分类结果"""

    query: str
    intent: QueryIntent
    confidence: float
    method: str  # rule, ml
    latency_ms: float = 0.0
    recommended_strategy: dict[str, any] = None  # 推荐的检索策略


class IntentClassifier:
    """意图分类器"""

    def __init__(self, method: str = "rule"):
        """
        初始化分类器

        Args:
            method: 分类方法 ("rule" or "ml")
        """
        self.method = method

        # 规则模式
        self.patterns = {
            QueryIntent.FACTUAL: [
                r"^什么是",
                r"^啥是",
                r"^.*的定义",
                r"^.*是什么",
                r"^什么叫",
            ],
            QueryIntent.HOWTO: [
                r"^如何",
                r"^怎么",
                r"^怎样",
                r"^.*的方法",
                r"^.*的步骤",
                r"^.*怎么做",
            ],
            QueryIntent.TROUBLESHOOTING: [
                r"^为什么.*失败",
                r"^为什么.*报错",
                r"^.*不work",
                r"^.*无法",
                r"^.*错误",
                r"^.*问题.*解决",
            ],
            QueryIntent.COMPARISON: [
                r".*和.*的区别",
                r".*与.*对比",
                r".*和.*哪个好",
                r"^比较.*和",
                r".*优缺点",
            ],
            QueryIntent.CONCEPTUAL: [
                r"^解释",
                r"^说明",
                r"^介绍",
                r"^.*原理",
                r"^.*机制",
            ],
        }

    async def classify(self, query: str) -> IntentResult:
        """
        分类查询意图

        Args:
            query: 用户查询

        Returns:
            分类结果
        """
        start_time = time.time()

        if self.method == "rule":
            intent, confidence = self._classify_by_rules(query)
        else:
            # 预留ML模型接口
            intent, confidence = self._classify_by_rules(query)

        # 生成推荐策略
        strategy = self._get_recommended_strategy(intent, query)

        latency_ms = (time.time() - start_time) * 1000

        return IntentResult(
            query=query,
            intent=intent,
            confidence=confidence,
            method=self.method,
            latency_ms=latency_ms,
            recommended_strategy=strategy,
        )

    def _classify_by_rules(self, query: str) -> tuple[QueryIntent, float]:
        """
        基于规则的分类

        Args:
            query: 用户查询

        Returns:
            (意图, 置信度)
        """
        # 遍历所有模式
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    return intent, 0.9  # 规则匹配的置信度固定

        # 开放式问题判断（长查询且无明确模式）
        if len(query) > 30 and not any(
            query.startswith(prefix)
            for prefix in ["什么", "如何", "为什么", "怎么"]
        ):
            return QueryIntent.OPENENDED, 0.6

        # 默认：未知
        return QueryIntent.UNKNOWN, 0.3

    def _get_recommended_strategy(
        self, intent: QueryIntent, query: str
    ) -> dict[str, any]:
        """
        根据意图推荐检索策略

        Args:
            intent: 查询意图
            query: 用户查询

        Returns:
            推荐策略配置
        """
        strategies = {
            QueryIntent.FACTUAL: {
                "retrieval_method": "vector",
                "enable_rerank": True,
                "enable_hyde": False,
                "vector_weight": 0.7,
                "bm25_weight": 0.3,
                "top_k": 10,
            },
            QueryIntent.HOWTO: {
                "retrieval_method": "hybrid",
                "enable_rerank": True,
                "enable_hyde": False,
                "vector_weight": 0.5,
                "bm25_weight": 0.5,
                "top_k": 15,
            },
            QueryIntent.TROUBLESHOOTING: {
                "retrieval_method": "hybrid",
                "enable_rerank": True,
                "enable_hyde": False,
                "vector_weight": 0.3,
                "bm25_weight": 0.7,  # 关键词更重要
                "top_k": 20,
            },
            QueryIntent.COMPARISON: {
                "retrieval_method": "hybrid",
                "enable_rerank": True,
                "enable_multi_query": True,
                "vector_weight": 0.6,
                "bm25_weight": 0.4,
                "top_k": 20,
            },
            QueryIntent.CONCEPTUAL: {
                "retrieval_method": "vector",
                "enable_rerank": True,
                "enable_hyde": True,
                "vector_weight": 0.8,
                "bm25_weight": 0.2,
                "top_k": 10,
            },
            QueryIntent.OPENENDED: {
                "retrieval_method": "hybrid",
                "enable_rerank": True,
                "enable_multi_query": True,
                "enable_query_expansion": True,
                "vector_weight": 0.6,
                "bm25_weight": 0.4,
                "top_k": 20,
            },
            QueryIntent.UNKNOWN: {
                "retrieval_method": "hybrid",
                "enable_rerank": False,
                "vector_weight": 0.5,
                "bm25_weight": 0.5,
                "top_k": 10,
            },
        }

        return strategies.get(intent, strategies[QueryIntent.UNKNOWN])

    async def classify_batch(self, queries: list[str]) -> list[IntentResult]:
        """批量分类"""
        import asyncio

        tasks = [self.classify(query) for query in queries]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "method": self.method,
            "num_intent_types": len(QueryIntent),
            "num_patterns": sum(len(patterns) for patterns in self.patterns.values()),
        }


# 使用示例
if __name__ == "__main__":
    import asyncio

    async def test():
        classifier = IntentClassifier(method="rule")

        test_queries = [
            "什么是量子计算？",
            "如何实现分布式锁？",
            "为什么Redis连接失败？",
            "Python和Java的区别是什么？",
            "解释一下微服务架构的原理",
            "我想了解机器学习在金融领域的应用场景和挑战",
        ]

        for query in test_queries:
            result = await classifier.classify(query)
            print(f"\n查询: {result.query}")
            print(f"意图: {result.intent.value}")
            print(f"置信度: {result.confidence}")
            print(f"推荐策略: {result.recommended_strategy['retrieval_method']}")
            print(f"延迟: {result.latency_ms:.2f}ms")

    asyncio.run(test())

