"""
Tiered Rerank Service - 分层重排序服务

功能:
- 分层重排，降低成本
- Tier 1 (top 20): Cross-Encoder (高精度)
- Tier 2 (21-50): 快速reranker
- Tier 3 (>50): 保持原序

目标:
- Rerank成本降低≥40%
- NDCG@10下降≤3%
"""

import asyncio
import time

from app.models.retrieval import RetrievalDocument
from app.observability.logging import logger


class TieredRerankService:
    """分层重排序服务"""

    def __init__(
        self,
        tier1_size: int = 20,
        tier2_size: int = 30,
        tier1_model: str = "cross-encoder",
        tier2_model: str = "bge-reranker-base",
    ):
        """
        初始化分层重排序

        Args:
            tier1_size: Tier 1大小（top N使用精排）
            tier2_size: Tier 2大小（使用快速排序）
            tier1_model: Tier 1模型
            tier2_model: Tier 2模型
        """
        self.tier1_size = tier1_size
        self.tier2_size = tier2_size
        self.tier1_model = tier1_model
        self.tier2_model = tier2_model

        logger.info(
            f"Tiered rerank service initialized: tier1_size={tier1_size}, tier2_size={tier2_size}"
        )

    async def rerank(
        self,
        query: str,
        documents: list[RetrievalDocument],
        final_top_k: int = 10,
    ) -> list[RetrievalDocument]:
        """
        分层重排序

        Args:
            query: 查询
            documents: 候选文档
            final_top_k: 最终返回数

        Returns:
            重排后文档
        """
        start_time = time.time()

        if not documents:
            return documents

        # 1. 划分tiers
        tier1_docs = documents[: self.tier1_size]
        tier2_docs = documents[self.tier1_size : self.tier1_size + self.tier2_size]
        tier3_docs = documents[self.tier1_size + self.tier2_size :]

        logger.info(
            f"Tiered rerank: tier1={len(tier1_docs)}, "
            f"tier2={len(tier2_docs)}, tier3={len(tier3_docs)}"
        )

        # 2. Tier 1: Cross-Encoder精排
        tier1_reranked = await self._tier1_rerank(query, tier1_docs)

        # 3. Tier 2: 快速rerank
        tier2_reranked = await self._tier2_rerank(query, tier2_docs)

        # 4. Tier 3: 保持原序
        tier3_kept = tier3_docs

        # 5. 合并
        all_reranked = tier1_reranked + tier2_reranked + tier3_kept

        # 6. 最终排序并截断
        all_reranked.sort(key=lambda d: d.score, reverse=True)
        final_docs = all_reranked[:final_top_k]

        latency_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Tiered rerank completed: {len(documents)} -> {len(final_docs)} in {latency_ms:.1f}ms"
        )

        return final_docs

    async def _tier1_rerank(
        self, _query: str, documents: list[RetrievalDocument]
    ) -> list[RetrievalDocument]:
        """Tier 1: Cross-Encoder精排"""
        if not documents:
            return documents

        # 模拟Cross-Encoder推理（耗时）
        await asyncio.sleep(0.01 * len(documents))

        # 重新打分
        for i, doc in enumerate(documents):
            # 模拟精确分数
            doc.score = 0.95 - i * 0.02

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents

    async def _tier2_rerank(
        self, _query: str, documents: list[RetrievalDocument]
    ) -> list[RetrievalDocument]:
        """Tier 2: 快速rerank"""
        if not documents:
            return documents

        # 模拟快速reranker（低延迟）
        await asyncio.sleep(0.003 * len(documents))

        # 简单调整分数
        for i, doc in enumerate(documents):
            doc.score = 0.85 - i * 0.01

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents

    async def estimate_cost(self, num_documents: int) -> dict:
        """
        估算成本

        Args:
            num_documents: 文档数量

        Returns:
            成本估算
        """
        # Tier 1成本（高）
        tier1_count = min(num_documents, self.tier1_size)
        tier1_cost = tier1_count * 0.00001  # $0.01 per 1K documents

        # Tier 2成本（低）
        tier2_count = min(max(0, num_documents - self.tier1_size), self.tier2_size)
        tier2_cost = tier2_count * 0.000002  # $0.002 per 1K documents

        # Tier 3成本（零）
        tier3_count = max(0, num_documents - self.tier1_size - self.tier2_size)
        tier3_cost = 0.0

        total_cost = tier1_cost + tier2_cost + tier3_cost

        return {
            "tier1_count": tier1_count,
            "tier1_cost": tier1_cost,
            "tier2_count": tier2_count,
            "tier2_cost": tier2_cost,
            "tier3_count": tier3_count,
            "tier3_cost": tier3_cost,
            "total_cost": total_cost,
        }

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "tier1_size": self.tier1_size,
            "tier2_size": self.tier2_size,
            "tier1_model": self.tier1_model,
            "tier2_model": self.tier2_model,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = TieredRerankService()

        # 创建测试文档
        docs = [
            RetrievalDocument(
                id=f"doc{i}",
                chunk_id=f"chunk{i}",
                content=f"Document {i}",
                score=0.8 - i * 0.01,
                metadata={},
            )
            for i in range(60)
        ]

        # 重排序
        query = "Python programming"
        reranked = await service.rerank(query, docs, final_top_k=10)

        print(f"Original: {len(docs)} docs")
        print(f"Reranked: {len(reranked)} docs")

        # 成本估算
        cost = await service.estimate_cost(len(docs))
        print(f"\nCost estimation: {cost}")

    asyncio.run(test())
