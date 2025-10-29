"""
检查点与恢复模块

支持 Agent 执行的断点续传和状态恢复。
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointStatus(Enum):
    """检查点状态"""

    ACTIVE = "active"  # 活跃（可恢复）
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    EXPIRED = "expired"  # 已过期


@dataclass
class Checkpoint:
    """检查点数据"""

    checkpoint_id: str
    task_id: str
    agent_id: str
    step_number: int
    state: dict[str, Any]  # 完整状态快照
    metadata: dict[str, Any]
    status: CheckpointStatus
    created_at: datetime
    expires_at: datetime | None = None


class CheckpointManager:
    """
    检查点管理器

    用法:
        manager = CheckpointManager(storage)

        # 保存检查点
        await manager.save_checkpoint(
            task_id="task_123",
            agent_id="agent_001",
            step_number=5,
            state={
                "current_step": "search_results",
                "variables": {...},
                "history": [...]
            }
        )

        # 恢复检查点
        state = await manager.restore_checkpoint(task_id="task_123")
    """

    def __init__(
        self,
        storage: Any,  # Redis/PostgreSQL
        checkpoint_interval: int = 5,  # 每N步保存一次
        retention_hours: int = 24,  # 保留时间
    ):
        """
        初始化检查点管理器

        Args:
            storage: 存储后端
            checkpoint_interval: 检查点间隔（步数）
            retention_hours: 检查点保留时间（小时）
        """
        self.storage = storage
        self.checkpoint_interval = checkpoint_interval
        self.retention_hours = retention_hours

        logger.info(
            f"CheckpointManager initialized (interval={checkpoint_interval} steps, "
            f"retention={retention_hours}h)"
        )

    async def save_checkpoint(
        self,
        task_id: str,
        agent_id: str,
        step_number: int,
        state: dict[str, Any],
        metadata: dict | None = None,
    ) -> str:
        """
        保存检查点

        Args:
            task_id: 任务 ID
            agent_id: Agent ID
            step_number: 步骤编号
            state: 状态数据
            metadata: 元数据

        Returns:
            检查点 ID
        """
        checkpoint_id = f"checkpoint_{task_id}_{step_number}"

        # 计算过期时间
        from datetime import timedelta

        expires_at = datetime.now() + timedelta(hours=self.retention_hours)

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            agent_id=agent_id,
            step_number=step_number,
            state=state,
            metadata=metadata or {},
            status=CheckpointStatus.ACTIVE,
            created_at=datetime.now(),
            expires_at=expires_at,
        )

        # 存储到后端
        await self._store_checkpoint(checkpoint)

        logger.info(
            f"[{task_id}] Checkpoint saved at step {step_number} (id={checkpoint_id})"
        )

        return checkpoint_id

    async def should_save_checkpoint(self, step_number: int) -> bool:
        """判断是否应该保存检查点"""
        return step_number % self.checkpoint_interval == 0

    async def restore_checkpoint(
        self, task_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        恢复检查点

        Args:
            task_id: 任务 ID
            checkpoint_id: 检查点 ID（可选，不提供则恢复最新的）

        Returns:
            状态数据，如果不存在返回 None
        """
        if checkpoint_id:
            checkpoint = await self._load_checkpoint(checkpoint_id)
        else:
            # 恢复最新的检查点
            checkpoint = await self._load_latest_checkpoint(task_id)

        if not checkpoint:
            logger.warning(f"No checkpoint found for task {task_id}")
            return None

        # 检查是否过期
        if checkpoint.expires_at and datetime.now() > checkpoint.expires_at:
            logger.warning(f"Checkpoint {checkpoint.checkpoint_id} has expired")
            checkpoint.status = CheckpointStatus.EXPIRED
            await self._update_checkpoint_status(checkpoint)
            return None

        logger.info(
            f"[{task_id}] Restored checkpoint from step {checkpoint.step_number}"
        )

        return checkpoint.state

    async def list_checkpoints(self, task_id: str) -> list[Checkpoint]:
        """列出任务的所有检查点"""
        checkpoints = await self._list_task_checkpoints(task_id)
        return sorted(checkpoints, key=lambda c: c.step_number)

    async def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点"""
        await self._delete_checkpoint(checkpoint_id)
        logger.info(f"Checkpoint deleted: {checkpoint_id}")

    async def mark_completed(self, task_id: str):
        """标记任务已完成（更新所有检查点状态）"""
        checkpoints = await self.list_checkpoints(task_id)
        for checkpoint in checkpoints:
            checkpoint.status = CheckpointStatus.COMPLETED
            await self._update_checkpoint_status(checkpoint)

        logger.info(f"[{task_id}] All checkpoints marked as completed")

    async def cleanup_expired(self):
        """清理过期的检查点"""
        # 实际项目中可以定期运行
        logger.info("Cleaning up expired checkpoints...")
        deleted_count = await self._cleanup_expired_checkpoints()
        logger.info(f"Cleaned up {deleted_count} expired checkpoints")

    # === 存储后端接口 ===

    async def _store_checkpoint(self, checkpoint: Checkpoint):
        """存储检查点到后端"""
        try:
            if hasattr(self.storage, "hset"):
                # Redis 实现
                key = f"checkpoint:{checkpoint.task_id}"
                field = checkpoint.checkpoint_id
                value = json.dumps(self._checkpoint_to_dict(checkpoint), default=str)
                await self.storage.hset(key, field, value)

                # 设置过期时间
                ttl = int(self.retention_hours * 3600)
                await self.storage.expire(key, ttl)

            elif hasattr(self.storage, "insert_checkpoint"):
                # PostgreSQL 实现
                await self.storage.insert_checkpoint(self._checkpoint_to_dict(checkpoint))

            else:
                logger.error("Storage backend does not support checkpoint operations")

        except Exception as e:
            logger.error(f"Error storing checkpoint: {e}")

    async def _load_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """从后端加载检查点"""
        try:
            if hasattr(self.storage, "hget"):
                # Redis 实现
                # 需要从 checkpoint_id 提取 task_id
                task_id = checkpoint_id.split("_")[1]  # 简化实现
                key = f"checkpoint:{task_id}"
                value = await self.storage.hget(key, checkpoint_id)

                if value:
                    data = json.loads(value.decode() if isinstance(value, bytes) else value)
                    return self._dict_to_checkpoint(data)

            elif hasattr(self.storage, "get_checkpoint"):
                # PostgreSQL 实现
                data = await self.storage.get_checkpoint(checkpoint_id)
                if data:
                    return self._dict_to_checkpoint(data)

            return None

        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            return None

    async def _load_latest_checkpoint(self, task_id: str) -> Checkpoint | None:
        """加载最新的检查点"""
        checkpoints = await self.list_checkpoints(task_id)
        active_checkpoints = [
            c for c in checkpoints if c.status == CheckpointStatus.ACTIVE
        ]

        if not active_checkpoints:
            return None

        # 返回步骤编号最大的
        return max(active_checkpoints, key=lambda c: c.step_number)

    async def _list_task_checkpoints(self, task_id: str) -> list[Checkpoint]:
        """列出任务的所有检查点"""
        try:
            if hasattr(self.storage, "hgetall"):
                # Redis 实现
                key = f"checkpoint:{task_id}"
                data = await self.storage.hgetall(key)

                checkpoints = []
                for value in data.values():
                    checkpoint_data = json.loads(
                        value.decode() if isinstance(value, bytes) else value
                    )
                    checkpoints.append(self._dict_to_checkpoint(checkpoint_data))

                return checkpoints

            elif hasattr(self.storage, "list_checkpoints"):
                # PostgreSQL 实现
                data_list = await self.storage.list_checkpoints(task_id)
                return [self._dict_to_checkpoint(d) for d in data_list]

            return []

        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")
            return []

    async def _delete_checkpoint(self, checkpoint_id: str):
        """删除检查点"""
        try:
            if hasattr(self.storage, "hdel"):
                # Redis 实现
                task_id = checkpoint_id.split("_")[1]
                key = f"checkpoint:{task_id}"
                await self.storage.hdel(key, checkpoint_id)

            elif hasattr(self.storage, "delete_checkpoint"):
                # PostgreSQL 实现
                await self.storage.delete_checkpoint(checkpoint_id)

        except Exception as e:
            logger.error(f"Error deleting checkpoint: {e}")

    async def _update_checkpoint_status(self, checkpoint: Checkpoint):
        """更新检查点状态"""
        # 重新存储
        await self._store_checkpoint(checkpoint)

    async def _cleanup_expired_checkpoints(self) -> int:
        """清理过期检查点"""
        # 简化实现：扫描所有检查点并删除过期的
        # 实际项目中应该使用数据库查询
        deleted_count = 0

        # 这里需要具体实现，取决于存储后端
        # 例如 Redis 可以使用 SCAN + 检查过期时间
        # PostgreSQL 可以使用 DELETE WHERE expires_at < NOW()

        return deleted_count

    def _checkpoint_to_dict(self, checkpoint: Checkpoint) -> dict:
        """检查点转字典"""
        data = asdict(checkpoint)
        data["status"] = checkpoint.status.value
        data["created_at"] = checkpoint.created_at.isoformat()
        if checkpoint.expires_at:
            data["expires_at"] = checkpoint.expires_at.isoformat()
        return data

    def _dict_to_checkpoint(self, data: dict) -> Checkpoint:
        """字典转检查点"""
        return Checkpoint(
            checkpoint_id=data["checkpoint_id"],
            task_id=data["task_id"],
            agent_id=data["agent_id"],
            step_number=data["step_number"],
            state=data["state"],
            metadata=data["metadata"],
            status=CheckpointStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )


class ResumableTask:
    """
    可恢复任务包装器

    用法:
        task = ResumableTask(checkpoint_manager, agent_engine)

        # 执行任务（自动保存检查点）
        result = await task.execute(
            task_id="task_123",
            task_description="Analyze this document",
            resume=True  # 尝试恢复
        )
    """

    def __init__(self, checkpoint_manager: CheckpointManager, agent_engine: Any):
        """
        初始化可恢复任务

        Args:
            checkpoint_manager: 检查点管理器
            agent_engine: Agent 引擎
        """
        self.checkpoint_manager = checkpoint_manager
        self.agent_engine = agent_engine

        logger.info("ResumableTask initialized")

    async def execute(
        self,
        task_id: str,
        task_description: str,
        resume: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        执行任务（支持恢复）

        Args:
            task_id: 任务 ID
            task_description: 任务描述
            resume: 是否尝试恢复
            **kwargs: 其他参数传递给 agent_engine

        Returns:
            执行结果
        """
        # 尝试恢复
        initial_state = None
        start_step = 0

        if resume:
            initial_state = await self.checkpoint_manager.restore_checkpoint(task_id)
            if initial_state:
                start_step = initial_state.get("step_number", 0) + 1
                logger.info(f"[{task_id}] Resuming from step {start_step}")

        # 执行任务（带检查点）
        result = await self._execute_with_checkpoints(
            task_id=task_id,
            task_description=task_description,
            initial_state=initial_state,
            start_step=start_step,
            **kwargs,
        )

        # 标记完成
        await self.checkpoint_manager.mark_completed(task_id)

        return result

    async def _execute_with_checkpoints(
        self,
        task_id: str,
        task_description: str,
        initial_state: dict | None,
        start_step: int,
        **kwargs,
    ) -> dict[str, Any]:
        """执行任务（自动保存检查点）"""
        # 这里需要与 AgentEngine 的执行流程集成
        # 简化实现：每N步保存检查点

        # 实际项目中，应该在 AgentEngine 的执行循环中插入检查点逻辑
        # 例如：
        # for step in range(start_step, max_steps):
        #     ... 执行一步 ...
        #
        #     if await self.checkpoint_manager.should_save_checkpoint(step):
        #         state = self._capture_state()
        #         await self.checkpoint_manager.save_checkpoint(task_id, agent_id, step, state)

        result = await self.agent_engine.execute(
            task=task_description, task_id=task_id, **kwargs
        )

        return result

