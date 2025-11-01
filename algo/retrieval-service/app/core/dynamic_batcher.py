"""
Dynamic Batcher - 动态批处理器

功能:
- 自适应批处理
- max_batch_size + max_wait_ms双阈值
- 异步Future模式

目标:
- QPS提升≥2x
- 单请求延迟增加≤20ms
"""

import asyncio
import contextlib
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from app.observability.logging import logger

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class BatchRequest(Generic[T]):
    """批请求"""

    data: T
    future: asyncio.Future
    timestamp: float


class DynamicBatcher(Generic[T, R]):
    """动态批处理器"""

    def __init__(
        self,
        batch_func: Callable[[list[T]], Coroutine[Any, Any, list[R]]],
        max_batch_size: int = 32,
        max_wait_ms: float = 50.0,
        name: str = "batcher",
    ):
        """
        初始化动态批处理器

        Args:
            batch_func: 批处理函数
            max_batch_size: 最大批大小
            max_wait_ms: 最大等待时间（毫秒）
            name: 批处理器名称
        """
        self.batch_func = batch_func
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self.name = name

        self.queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

        # 统计
        self._stats = {
            "total_requests": 0,
            "total_batches": 0,
            "avg_batch_size": 0.0,
            "avg_wait_ms": 0.0,
        }

        logger.info(
            f"Dynamic batcher '{name}' initialized: "
            f"max_batch_size={max_batch_size}, max_wait_ms={max_wait_ms}"
        )

    async def start(self):
        """启动批处理worker"""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._batch_worker())
            logger.info(f"Batcher '{self.name}' started")

    async def stop(self):
        """停止批处理worker"""
        if self._running:
            self._running = False
            if self._worker_task:
                self._worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._worker_task
            logger.info(f"Batcher '{self.name}' stopped")

    async def process(self, data: T) -> R:
        """
        处理单个请求（异步）

        Args:
            data: 请求数据

        Returns:
            处理结果
        """
        # 创建Future
        future = asyncio.get_event_loop().create_future()

        # 创建批请求
        request = BatchRequest(data=data, future=future, timestamp=time.time())

        # 加入队列
        await self.queue.put(request)

        # 等待结果
        result = await future
        return result

    async def _batch_worker(self):
        """批处理worker"""
        logger.info(f"Batch worker '{self.name}' started")

        while self._running:
            try:
                # 收集批次
                batch = await self._collect_batch()

                if batch:
                    # 处理批次
                    await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch worker error: {e}", exc_info=True)
                await asyncio.sleep(0.1)

        logger.info(f"Batch worker '{self.name}' stopped")

    async def _collect_batch(self) -> list[BatchRequest]:
        """
        收集批次

        Returns:
            批请求列表
        """
        batch: list[BatchRequest] = []
        deadline = time.time() + self.max_wait_ms / 1000.0

        # 等待第一个请求
        try:
            first_req = await asyncio.wait_for(self.queue.get(), timeout=self.max_wait_ms / 1000.0)
            batch.append(first_req)
        except TimeoutError:
            return batch

        # 收集更多请求直到达到batch_size或超时
        while len(batch) < self.max_batch_size:
            remaining_time = deadline - time.time()

            if remaining_time <= 0:
                break

            try:
                req = await asyncio.wait_for(self.queue.get(), timeout=remaining_time)
                batch.append(req)
            except TimeoutError:
                break

        return batch

    async def _process_batch(self, batch: list[BatchRequest]):
        """
        处理批次

        Args:
            batch: 批请求列表
        """
        start_time = time.time()

        try:
            # 提取数据
            batch_data = [req.data for req in batch]

            # 执行批处理
            results = await self.batch_func(batch_data)

            # 设置结果
            for req, result in zip(batch, results, strict=False):
                if not req.future.done():
                    req.future.set_result(result)

            # 更新统计
            processing_time = (time.time() - start_time) * 1000
            self._update_stats(len(batch), processing_time)

            logger.debug(
                f"Batch processed: {len(batch)} requests in {processing_time:.1f}ms "
                f"(avg wait: {sum(start_time - req.timestamp for req in batch) / len(batch) * 1000:.1f}ms)"
            )

        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)

            # 设置异常
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)

    def _update_stats(self, batch_size: int, processing_time_ms: float):
        """更新统计"""
        self._stats["total_requests"] += batch_size
        self._stats["total_batches"] += 1

        # 计算平均值
        total_batches = self._stats["total_batches"]
        self._stats["avg_batch_size"] = self._stats["total_requests"] / total_batches
        self._stats["avg_wait_ms"] = (
            self._stats["avg_wait_ms"] * (total_batches - 1) + processing_time_ms
        ) / total_batches

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "queue_size": self.queue.qsize(),
            **self._stats,
        }


# 使用示例
if __name__ == "__main__":

    async def batch_embedding_func(queries: list[str]) -> list[list[float]]:
        """模拟批量embedding"""
        await asyncio.sleep(0.05)  # 模拟批处理延迟
        return [[1.0] * 384 for _ in queries]

    async def test():
        # 创建batcher
        batcher = DynamicBatcher(
            batch_func=batch_embedding_func,
            max_batch_size=32,
            max_wait_ms=50,
            name="embedding_batcher",
        )

        await batcher.start()

        # 发送请求
        queries = [f"query_{i}" for i in range(100)]
        tasks = [batcher.process(q) for q in queries]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        print(f"Processed {len(results)} requests in {elapsed:.2f}s")
        print(f"QPS: {len(results) / elapsed:.1f}")
        print(f"Stats: {batcher.get_stats()}")

        await batcher.stop()

    asyncio.run(test())
