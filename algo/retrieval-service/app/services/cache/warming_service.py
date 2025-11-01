"""
Cache Warming Service - 缓存预热服务

功能:
- 高频query定时预加载
- 分析查询日志提取热点
- 批量预热缓存
- 缓存命中率监控

调度:
- 每日凌晨2:00执行
- 预热top 1000高频queries
"""

import asyncio
import time
from collections import Counter
from typing import List, Optional

from app.infrastructure.semantic_cache import get_semantic_cache
from app.observability.logging import logger


class CacheWarmingService:
    """缓存预热服务"""

    def __init__(
        self,
        top_k_queries: int = 1000,
        batch_size: int = 50,
        concurrent_limit: int = 10,
    ):
        """
        初始化缓存预热服务

        Args:
            top_k_queries: 预热的高频query数量
            batch_size: 批处理大小
            concurrent_limit: 并发限制
        """
        self.top_k_queries = top_k_queries
        self.batch_size = batch_size
        self.concurrent_limit = concurrent_limit
        self.semantic_cache = get_semantic_cache()

        logger.info(
            f"Cache warming service initialized: top_k={top_k_queries}, "
            f"batch_size={batch_size}, concurrent={concurrent_limit}"
        )

    async def warm_cache(self, query_log_path: Optional[str] = None) -> dict:
        """
        执行缓存预热

        Args:
            query_log_path: 查询日志路径（可选）

        Returns:
            预热统计
        """
        start_time = time.time()
        logger.info("Starting cache warming...")

        try:
            # 1. 提取高频queries
            hot_queries = await self.extract_hot_queries(query_log_path)
            logger.info(f"Extracted {len(hot_queries)} hot queries")

            # 2. 批量预热
            warmed_count = 0
            failed_count = 0

            for i in range(0, len(hot_queries), self.batch_size):
                batch = hot_queries[i : i + self.batch_size]

                # 并发执行预热
                tasks = []
                for query in batch:
                    task = self._warm_single_query(query)
                    tasks.append(task)

                    # 控制并发数
                    if len(tasks) >= self.concurrent_limit:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for result in results:
                            if isinstance(result, Exception):
                                failed_count += 1
                            else:
                                warmed_count += 1
                        tasks = []

                # 处理剩余任务
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            failed_count += 1
                        else:
                            warmed_count += 1

                logger.info(f"Warmed batch {i // self.batch_size + 1}")

            elapsed = time.time() - start_time

            stats = {
                "total_queries": len(hot_queries),
                "warmed_count": warmed_count,
                "failed_count": failed_count,
                "elapsed_seconds": elapsed,
                "queries_per_second": len(hot_queries) / elapsed if elapsed > 0 else 0,
            }

            logger.info(
                f"Cache warming completed: {warmed_count} queries warmed "
                f"in {elapsed:.1f}s ({stats['queries_per_second']:.1f} qps)"
            )

            return stats

        except Exception as e:
            logger.error(f"Cache warming failed: {e}", exc_info=True)
            return {
                "error": str(e),
                "total_queries": 0,
                "warmed_count": 0,
                "failed_count": 0,
            }

    async def extract_hot_queries(
        self, query_log_path: Optional[str] = None
    ) -> List[str]:
        """
        从查询日志提取高频queries

        Args:
            query_log_path: 查询日志路径

        Returns:
            高频query列表
        """
        if query_log_path:
            # 从文件读取
            return await self._extract_from_file(query_log_path)
        else:
            # 从Redis/数据库读取
            return await self._extract_from_redis()

    async def _extract_from_file(self, log_path: str) -> List[str]:
        """从日志文件提取"""
        try:
            # 读取日志文件
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 统计查询频率
            query_counter = Counter()
            for line in lines:
                # 假设格式: timestamp|query|...
                parts = line.strip().split("|")
                if len(parts) >= 2:
                    query = parts[1]
                    query_counter[query] += 1

            # 返回top-k
            hot_queries = [q for q, _ in query_counter.most_common(self.top_k_queries)]
            return hot_queries

        except Exception as e:
            logger.error(f"Failed to extract from file: {e}")
            return []

    async def _extract_from_redis(self) -> List[str]:
        """从Redis提取（模拟实现）"""
        # 实际应该从Redis或时序数据库读取查询统计
        # 这里返回模拟数据
        hot_queries = [
            "Python programming tutorial",
            "机器学习入门",
            "深度学习框架对比",
            "数据分析工具",
            "云计算架构",
            "微服务设计模式",
            "Docker容器化部署",
            "Kubernetes集群管理",
            "前端框架选择",
            "后端API设计",
        ]
        return hot_queries[: self.top_k_queries]

    async def _warm_single_query(self, query: str) -> bool:
        """
        预热单个query

        Args:
            query: 查询文本

        Returns:
            是否成功
        """
        try:
            # 这里应该调用实际的检索服务
            # 获取结果并缓存
            # 简化实现：模拟延迟
            await asyncio.sleep(0.05)

            # 模拟embedding
            import numpy as np

            query_embedding = np.random.randn(384).astype(np.float32)

            # 模拟检索结果
            documents = [
                {
                    "id": f"doc_{i}",
                    "content": f"Document {i} for query: {query}",
                    "score": 0.9 - i * 0.1,
                }
                for i in range(5)
            ]

            # 写入缓存
            await self.semantic_cache.set(query, query_embedding, documents)

            return True

        except Exception as e:
            logger.warning(f"Failed to warm query '{query}': {e}")
            return False

    async def schedule_warming(self):
        """
        调度定时预热

        每日凌晨2:00执行
        """
        import datetime

        logger.info("Cache warming scheduler started")

        while True:
            try:
                # 计算下次执行时间
                now = datetime.datetime.now()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)

                if now.hour >= 2:
                    # 今天已经执行过，等到明天
                    next_run += datetime.timedelta(days=1)

                wait_seconds = (next_run - now).total_seconds()

                logger.info(
                    f"Next cache warming scheduled at {next_run} "
                    f"(in {wait_seconds / 3600:.1f} hours)"
                )

                # 等待
                await asyncio.sleep(wait_seconds)

                # 执行预热
                stats = await self.warm_cache()
                logger.info(f"Scheduled warming completed: {stats}")

            except Exception as e:
                logger.error(f"Scheduled warming error: {e}", exc_info=True)
                await asyncio.sleep(3600)  # 出错后1小时重试

    async def get_warming_stats(self) -> dict:
        """获取预热统计"""
        cache_stats = await self.semantic_cache.get_stats()

        return {
            "cache_stats": cache_stats,
            "top_k_queries": self.top_k_queries,
            "batch_size": self.batch_size,
            "concurrent_limit": self.concurrent_limit,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = CacheWarmingService(top_k_queries=10)

        # 执行一次预热
        stats = await service.warm_cache()
        print(f"Warming stats: {stats}")

        # 查看缓存统计
        warming_stats = await service.get_warming_stats()
        print(f"Warming service stats: {warming_stats}")

    asyncio.run(test())
