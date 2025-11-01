"""
索引任务队列
基于 Redis 实现优先级队列、任务状态追踪和重试机制
"""

import asyncio
import json
import logging
import time
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Prometheus 指标
TASKS_ENQUEUED = Counter(
    "indexing_tasks_enqueued_total",
    "Total number of tasks enqueued",
    ["priority", "tenant_id"],
)
TASKS_PROCESSED = Counter(
    "indexing_tasks_processed_total",
    "Total number of tasks processed",
    ["status", "priority"],
)
QUEUE_SIZE = Gauge(
    "indexing_queue_size",
    "Current size of the indexing queue",
    ["priority"],
)
TASK_WAIT_TIME = Histogram(
    "indexing_task_wait_seconds",
    "Time tasks spend waiting in queue",
    ["priority"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
)


class TaskPriority(Enum):
    """任务优先级"""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class IndexingTask:
    """索引任务"""

    def __init__(
        self,
        task_id: str,
        document_id: str,
        tenant_id: str = "default",
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: dict[str, Any] | None = None,
        max_retries: int = 3,
    ):
        """
        初始化索引任务

        Args:
            task_id: 任务 ID
            document_id: 文档 ID
            tenant_id: 租户 ID
            priority: 任务优先级
            metadata: 任务元数据
            max_retries: 最大重试次数
        """
        self.task_id = task_id
        self.document_id = document_id
        self.tenant_id = tenant_id
        self.priority = priority
        self.metadata = metadata or {}
        self.max_retries = max_retries

        self.status = TaskStatus.PENDING
        self.retry_count = 0
        self.error_message = None
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "document_id": self.document_id,
            "tenant_id": self.tenant_id,
            "priority": self.priority.value,
            "status": self.status.value,
            "metadata": self.metadata,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexingTask":
        """从字典创建任务"""
        task = cls(
            task_id=data["task_id"],
            document_id=data["document_id"],
            tenant_id=data.get("tenant_id", "default"),
            priority=TaskPriority(data.get("priority", 1)),
            metadata=data.get("metadata", {}),
            max_retries=data.get("max_retries", 3),
        )

        task.status = TaskStatus(data.get("status", "pending"))
        task.retry_count = data.get("retry_count", 0)
        task.error_message = data.get("error_message")
        task.created_at = data.get("created_at", time.time())
        task.started_at = data.get("started_at")
        task.completed_at = data.get("completed_at")

        return task


class IndexingTaskQueue:
    """索引任务队列（基于 Redis）"""

    def __init__(
        self,
        redis_client,
        queue_prefix: str = "indexing:queue",
        task_prefix: str = "indexing:task",
        max_queue_size: int = 10000,
    ):
        """
        初始化任务队列

        Args:
            redis_client: Redis 客户端
            queue_prefix: 队列键前缀
            task_prefix: 任务键前缀
            max_queue_size: 最大队列大小
        """
        self.redis = redis_client
        self.queue_prefix = queue_prefix
        self.task_prefix = task_prefix
        self.max_queue_size = max_queue_size

        # 优先级队列键
        self.queue_keys = {
            TaskPriority.URGENT: f"{queue_prefix}:urgent",
            TaskPriority.HIGH: f"{queue_prefix}:high",
            TaskPriority.MEDIUM: f"{queue_prefix}:medium",
            TaskPriority.LOW: f"{queue_prefix}:low",
        }

        logger.info(f"IndexingTaskQueue initialized: max_size={max_queue_size}")

    async def enqueue(
        self,
        document_id: str,
        tenant_id: str = "default",
        priority: TaskPriority = TaskPriority.MEDIUM,
        metadata: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> IndexingTask:
        """
        将任务加入队列

        Args:
            document_id: 文档 ID
            tenant_id: 租户 ID
            priority: 任务优先级
            metadata: 任务元数据
            max_retries: 最大重试次数

        Returns:
            IndexingTask
        """
        # 生成任务 ID
        task_id = f"{tenant_id}:{document_id}:{int(time.time() * 1000)}"

        # 创建任务
        task = IndexingTask(
            task_id=task_id,
            document_id=document_id,
            tenant_id=tenant_id,
            priority=priority,
            metadata=metadata,
            max_retries=max_retries,
        )

        # 检查队列大小
        queue_key = self.queue_keys[priority]
        queue_size = await self.redis.llen(queue_key)

        if queue_size >= self.max_queue_size:
            logger.warning(f"Queue size limit reached: {queue_size} >= {self.max_queue_size}")
            raise ValueError(f"Queue is full (size={queue_size})")

        # 保存任务状态
        task_key = f"{self.task_prefix}:{task_id}"
        await self.redis.setex(
            task_key,
            86400,  # TTL: 24小时
            json.dumps(task.to_dict()),
        )

        # 加入优先级队列
        await self.redis.rpush(queue_key, task_id)

        # 更新指标
        TASKS_ENQUEUED.labels(
            priority=priority.name,
            tenant_id=tenant_id,
        ).inc()

        QUEUE_SIZE.labels(priority=priority.name).set(await self.redis.llen(queue_key))

        logger.info(
            f"Task enqueued: {task_id} (priority={priority.name}, "
            f"document={document_id}, tenant={tenant_id})"
        )

        return task

    async def dequeue(self) -> IndexingTask | None:
        """
        从队列中取出任务（按优先级）

        Returns:
            IndexingTask 或 None
        """
        # 按优先级顺序检查队列
        for priority in [
            TaskPriority.URGENT,
            TaskPriority.HIGH,
            TaskPriority.MEDIUM,
            TaskPriority.LOW,
        ]:
            queue_key = self.queue_keys[priority]

            # 原子操作：从队列头部取出任务
            task_id = await self.redis.lpop(queue_key)

            if task_id:
                # 更新队列大小指标
                QUEUE_SIZE.labels(priority=priority.name).set(await self.redis.llen(queue_key))

                # 获取任务详情
                task = await self.get_task(task_id)

                if task:
                    # 更新任务状态
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()
                    await self.update_task(task)

                    # 记录等待时间
                    wait_time = task.started_at - task.created_at
                    TASK_WAIT_TIME.labels(priority=priority.name).observe(wait_time)

                    logger.info(
                        f"Task dequeued: {task_id} (priority={priority.name}, "
                        f"wait_time={wait_time:.2f}s)"
                    )

                    return task

        return None

    async def get_task(self, task_id: str) -> IndexingTask | None:
        """
        获取任务详情

        Args:
            task_id: 任务 ID

        Returns:
            IndexingTask 或 None
        """
        task_key = f"{self.task_prefix}:{task_id}"
        task_data = await self.redis.get(task_key)

        if task_data:
            return IndexingTask.from_dict(json.loads(task_data))

        return None

    async def update_task(self, task: IndexingTask):
        """
        更新任务状态

        Args:
            task: IndexingTask
        """
        task_key = f"{self.task_prefix}:{task.task_id}"
        await self.redis.setex(
            task_key,
            86400,  # TTL: 24小时
            json.dumps(task.to_dict()),
        )

    async def mark_success(self, task: IndexingTask):
        """
        标记任务成功

        Args:
            task: IndexingTask
        """
        task.status = TaskStatus.SUCCESS
        task.completed_at = time.time()
        await self.update_task(task)

        TASKS_PROCESSED.labels(
            status="success",
            priority=task.priority.name,
        ).inc()

        logger.info(f"Task succeeded: {task.task_id}")

    async def mark_failed(
        self,
        task: IndexingTask,
        error_message: str,
        retry: bool = True,
    ):
        """
        标记任务失败

        Args:
            task: IndexingTask
            error_message: 错误消息
            retry: 是否重试
        """
        task.error_message = error_message
        task.retry_count += 1

        # 判断是否需要重试
        if retry and task.retry_count < task.max_retries:
            task.status = TaskStatus.RETRYING

            # 重新加入队列（降低优先级）
            priority = TaskPriority.LOW if task.priority != TaskPriority.LOW else TaskPriority.LOW
            queue_key = self.queue_keys[priority]
            await self.redis.rpush(queue_key, task.task_id)

            logger.warning(
                f"Task failed, retrying: {task.task_id} "
                f"(retry_count={task.retry_count}/{task.max_retries})"
            )

        else:
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()

            TASKS_PROCESSED.labels(
                status="failed",
                priority=task.priority.name,
            ).inc()

            logger.error(
                f"Task failed permanently: {task.task_id} "
                f"(retry_count={task.retry_count}, error={error_message})"
            )

        await self.update_task(task)

    async def get_queue_stats(self) -> dict[str, Any]:
        """
        获取队列统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "queue_sizes": {},
            "total_size": 0,
        }

        for priority, queue_key in self.queue_keys.items():
            size = await self.redis.llen(queue_key)
            stats["queue_sizes"][priority.name] = size
            stats["total_size"] += size

        return stats

    async def clear_queue(self, priority: TaskPriority | None = None):
        """
        清空队列

        Args:
            priority: 指定优先级队列，None 表示清空所有队列
        """
        if priority:
            queue_key = self.queue_keys[priority]
            await self.redis.delete(queue_key)
            logger.info(f"Cleared queue: {priority.name}")
        else:
            for queue_key in self.queue_keys.values():
                await self.redis.delete(queue_key)
            logger.info("Cleared all queues")

    async def cancel_task(self, task_id: str):
        """
        取消任务

        Args:
            task_id: 任务 ID
        """
        task = await self.get_task(task_id)

        if task:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            await self.update_task(task)

            logger.info(f"Task cancelled: {task_id}")


class TaskQueueWorker:
    """任务队列工作器"""

    def __init__(
        self,
        task_queue: IndexingTaskQueue,
        document_processor,
        worker_id: str = "worker-1",
        poll_interval: float = 1.0,
    ):
        """
        初始化工作器

        Args:
            task_queue: 任务队列
            document_processor: 文档处理器
            worker_id: 工作器 ID
            poll_interval: 轮询间隔（秒）
        """
        self.task_queue = task_queue
        self.document_processor = document_processor
        self.worker_id = worker_id
        self.poll_interval = poll_interval

        self._running = False

        logger.info(f"TaskQueueWorker initialized: {worker_id}")

    async def start(self):
        """启动工作器"""
        self._running = True
        logger.info(f"Worker {self.worker_id} started")

        while self._running:
            try:
                # 从队列取任务
                task = await self.task_queue.dequeue()

                if task:
                    # 处理任务
                    await self._process_task(task)
                else:
                    # 队列为空，等待
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """停止工作器"""
        self._running = False
        logger.info(f"Worker {self.worker_id} stopped")

    async def _process_task(self, task: IndexingTask):
        """
        处理任务

        Args:
            task: IndexingTask
        """
        try:
            logger.info(
                f"Worker {self.worker_id} processing task: {task.task_id} "
                f"(document={task.document_id})"
            )

            # 调用文档处理器
            result = await self.document_processor.process_document(
                document_id=task.document_id,
                tenant_id=task.tenant_id,
                user_id=task.metadata.get("user_id"),
                file_path=task.metadata.get("file_path"),
            )

            # 标记任务完成
            if result.get("status") == "success":
                await self.task_queue.mark_success(task)
            else:
                await self.task_queue.mark_failed(
                    task,
                    error_message=result.get("error", "Unknown error"),
                    retry=True,
                )

        except Exception as e:
            logger.error(f"Task processing failed: {e}", exc_info=True)
            await self.task_queue.mark_failed(
                task,
                error_message=str(e),
                retry=True,
            )
