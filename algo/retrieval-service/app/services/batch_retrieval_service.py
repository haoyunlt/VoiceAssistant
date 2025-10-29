"""
Batch Retrieval Service - 批量检索服务

功能:
- 批量处理多个查询
- 并发执行，提升吞吐量
- 智能批处理和资源调度

目标:
- 批量吞吐提升≥3x
- P95延迟<500ms (10 queries)
"""

import asyncio
import time
from dataclasses import dataclass

from app.core.logging import logger
from app.models.retrieval import HybridRequest, HybridResponse
from app.services.retrieval_service import RetrievalService


@dataclass
class BatchRequest:
    """批量检索请求"""

    queries: list[HybridRequest]
    max_concurrency: int = 10  # 最大并发数


@dataclass
class BatchResponse:
    """批量检索响应"""

    results: list[HybridResponse]
    total_queries: int
    successful: int
    failed: int
    total_latency_ms: float
    avg_latency_per_query: float


class BatchRetrievalService:
    """批量检索服务"""

    def __init__(
        self,
        retrieval_service: RetrievalService,
        max_concurrency: int = 10,
        batch_size: int = 50,
    ):
        """
        初始化批量检索服务

        Args:
            retrieval_service: 检索服务实例
            max_concurrency: 最大并发数
            batch_size: 批处理大小
        """
        self.retrieval_service = retrieval_service
        self.max_concurrency = max_concurrency
        self.batch_size = batch_size

        logger.info(
            f"Batch retrieval service initialized: "
            f"max_concurrency={max_concurrency}, batch_size={batch_size}"
        )

    async def batch_search(
        self, requests: list[HybridRequest], max_concurrency: int = None
    ) -> BatchResponse:
        """
        批量检索

        Args:
            requests: 检索请求列表
            max_concurrency: 最大并发数（覆盖默认值）

        Returns:
            批量检索响应
        """
        start_time = time.time()
        total_queries = len(requests)

        if not requests:
            return BatchResponse(
                results=[],
                total_queries=0,
                successful=0,
                failed=0,
                total_latency_ms=0,
                avg_latency_per_query=0,
            )

        # 使用semaphore限制并发
        concurrency = max_concurrency or self.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def search_with_semaphore(request: HybridRequest):
            async with semaphore:
                try:
                    return await self.retrieval_service.hybrid_search(request), None
                except Exception as e:
                    logger.error(f"Batch search failed for query '{request.query[:50]}': {e}")
                    return None, str(e)

        # 并发执行所有查询
        tasks = [search_with_semaphore(req) for req in requests]
        results_with_errors = await asyncio.gather(*tasks)

        # 分离成功和失败的结果
        results = []
        successful = 0
        failed = 0

        for result, _error in results_with_errors:
            if result:
                results.append(result)
                successful += 1
            else:
                failed += 1

        total_latency_ms = (time.time() - start_time) * 1000
        avg_latency = total_latency_ms / total_queries if total_queries > 0 else 0

        logger.info(
            f"Batch search completed: {total_queries} queries, "
            f"{successful} successful, {failed} failed, "
            f"total={total_latency_ms:.1f}ms, avg={avg_latency:.1f}ms/query"
        )

        return BatchResponse(
            results=results,
            total_queries=total_queries,
            successful=successful,
            failed=failed,
            total_latency_ms=total_latency_ms,
            avg_latency_per_query=avg_latency,
        )

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "max_concurrency": self.max_concurrency,
            "batch_size": self.batch_size,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        from app.services.retrieval_service import RetrievalService

        retrieval_service = RetrievalService()
        batch_service = BatchRetrievalService(
            retrieval_service=retrieval_service, max_concurrency=5
        )

        # 创建测试请求
        requests = [HybridRequest(query=f"Query {i}", top_k=10) for i in range(10)]

        # 批量检索
        response = await batch_service.batch_search(requests)

        print(f"Total queries: {response.total_queries}")
        print(f"Successful: {response.successful}")
        print(f"Failed: {response.failed}")
        print(f"Total latency: {response.total_latency_ms:.1f}ms")
        print(f"Avg latency: {response.avg_latency_per_query:.1f}ms/query")

    # asyncio.run(test())
    print("✅ Batch Retrieval Service implemented")
