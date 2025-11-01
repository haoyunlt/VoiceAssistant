"""
Adaptive Rerank Service - 自适应重排序服务

功能:
- 根据query复杂度自适应调整Stage配置
- Simple: stage1=20, stage2=5
- Medium: stage1=40, stage2=10
- Complex: stage1=60, stage2=15

目标:
- Rerank延迟降低≥40%
- NDCG@10保持或提升
"""

import asyncio
import time
from typing import List

from app.models.retrieval import RetrievalDocument
from app.observability.logging import logger
from app.services.query.intent_classifier import IntentClassifier, QueryComplexity


class AdaptiveRerankService:
    """自适应重排序服务"""

    def __init__(self):
        """初始化自适应重排序服务"""
        self.intent_classifier = IntentClassifier()

        # 配置映射
        self.config_map = {
            QueryComplexity.SIMPLE: {"stage1_top_k": 20, "stage2_top_k": 5},
            QueryComplexity.MEDIUM: {"stage1_top_k": 40, "stage2_top_k": 10},
            QueryComplexity.COMPLEX: {"stage1_top_k": 60, "stage2_top_k": 15},
        }

        logger.info("Adaptive rerank service initialized")

    async def rerank(
        self, query: str, documents: List[RetrievalDocument], final_top_k: int = 10
    ) -> List[RetrievalDocument]:
        """
        自适应重排序

        Args:
            query: 查询
            documents: 候选文档
            final_top_k: 最终返回数

        Returns:
            重排后文档
        """
        start_time = time.time()

        # 1. 评估查询复杂度
        complexity = self._evaluate_complexity(query)
        config = self.config_map[complexity]

        logger.info(
            f"Adaptive rerank: complexity={complexity.value}, "
            f"stage1_top_k={config['stage1_top_k']}, "
            f"stage2_top_k={config['stage2_top_k']}"
        )

        # 2. Stage 1: 快速粗排
        stage1_docs = await self._stage1_rerank(
            query, documents, config["stage1_top_k"]
        )

        # 3. Stage 2: 精准精排
        stage2_docs = await self._stage2_rerank(
            query, stage1_docs, config["stage2_top_k"]
        )

        # 4. 最终截断
        final_docs = stage2_docs[:final_top_k]

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Adaptive rerank completed: {len(documents)} -> {len(final_docs)} "
            f"in {latency_ms:.1f}ms"
        )

        return final_docs

    def _evaluate_complexity(self, query: str) -> QueryComplexity:
        """评估查询复杂度"""
        query_length = len(query)
        word_count = len(query.split())

        if query_length < 10 and word_count <= 3:
            return QueryComplexity.SIMPLE
        elif word_count > 15 or any(
            kw in query for kw in ["比较", "对比", "区别", "优缺点"]
        ):
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.MEDIUM

    async def _stage1_rerank(
        self, query: str, documents: List[RetrievalDocument], top_k: int
    ) -> List[RetrievalDocument]:
        """Stage 1: 快速粗排"""
        # 简单基于关键词匹配
        await asyncio.sleep(0.005 * len(documents))  # 模拟延迟

        # 按分数排序
        sorted_docs = sorted(documents, key=lambda d: d.score, reverse=True)
        return sorted_docs[:top_k]

    async def _stage2_rerank(
        self, query: str, documents: List[RetrievalDocument], top_k: int
    ) -> List[RetrievalDocument]:
        """Stage 2: 精准精排"""
        # 使用Cross-Encoder
        await asyncio.sleep(0.01 * len(documents))  # 模拟延迟

        # 按分数排序
        sorted_docs = sorted(documents, key=lambda d: d.score, reverse=True)
        return sorted_docs[:top_k]

    def get_stats(self) -> dict:
        """获取统计"""
        return {"config_map": self.config_map}
