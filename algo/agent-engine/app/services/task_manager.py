"""任务状态管理服务（Redis持久化）"""

import json
import logging
from datetime import datetime

import redis.asyncio as redis  # type: ignore

from app.core.config import settings
from app.models.agent import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """任务状态管理器（Redis持久化）"""

    def __init__(self) -> None:
        self.redis_client: redis.Redis | None = None
        self.task_prefix = "agent:task:"
        self.task_list_key = "agent:tasks:list"
        self.task_ttl = 86400 * 7  # 7天

    async def initialize(self) -> None:
        """初始化Redis连接"""
        try:
            redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
            self.redis_client = await redis.from_url(
                redis_url, decode_responses=True, encoding="utf-8"
            )
            # 测试连接
            await self.redis_client.ping()
            logger.info("TaskManager Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("TaskManager will operate in memory-only mode")
            self.redis_client = None

    async def close(self) -> None:
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()

    def _serialize_result(self, result: AgentResult) -> bytes:
        """序列化AgentResult为JSON"""
        data = {
            "task_id": result.task_id,
            "result": result.result,
            "steps": [
                {
                    "step_number": step.step_number if step.step_number else 0,
                    "step_type": step.step_type.value
                    if isinstance(step.step_type, StepType)
                    else step.step_type.value,
                    "content": step.content if step.content else "",
                    "tool_name": step.tool_name if step.tool_name else "",
                    "tool_input": step.tool_input if step.tool_input else "",
                    "tool_output": step.tool_output if step.tool_output else "",
                    "timestamp": step.timestamp.isoformat() if step.timestamp else "",
                }  # type: ignore
                for step in (result.steps or [])
            ],
            "status": result.status.value
            if isinstance(result.status, AgentStatus)
            else result.status.value,
            "error": result.error,
            "iterations": result.iterations,
            "execution_time": result.execution_time,
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def _deserialize_result(self, data_bytes: bytes) -> AgentResult:
        """反序列化JSON为AgentResult"""
        data = json.loads(data_bytes.decode("utf-8"))

        # 重建steps
        from app.models.agent import AgentStep, StepType

        steps = []
        for step_data in data.get("steps", []):
            step = AgentStep(
                step_number=step_data["step_number"],
                step_type=StepType(step_data["step_type"])
                if isinstance(step_data["step_type"], str)
                else step_data["step_type"],
                content=step_data["content"],
                tool_name=step_data.get("tool_name"),
                tool_input=step_data.get("tool_input"),
                tool_output=step_data.get("tool_output"),
                timestamp=datetime.fromisoformat(step_data["timestamp"])
                if step_data.get("timestamp")
                else datetime.utcnow(),
            )
            steps.append(step)

        # 重建AgentResult
        result = AgentResult(
            task_id=data["task_id"],
            result=data.get("result"),
            steps=steps,
            status=AgentStatus(data["status"])
            if isinstance(data["status"], str)
            else data["status"],
            error=data.get("error"),
            iterations=data.get("iterations", 0),
            execution_time=data.get("execution_time", 0.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
        )
        return result

    async def save_task(self, result: AgentResult) -> bool:
        """保存任务状态到Redis"""
        if not self.redis_client:
            logger.warning(f"Redis not available, task {result.task_id} not persisted")
            return False

        try:
            key = f"{self.task_prefix}{result.task_id}"
            data = self._serialize_result(result)

            # 保存任务数据
            await self.redis_client.setex(key, self.task_ttl, data)

            # 添加到任务列表（用于查询所有任务）
            await self.redis_client.zadd(
                self.task_list_key, {result.task_id: datetime.utcnow().timestamp()}
            )

            logger.info(f"Task {result.task_id} saved to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to save task {result.task_id}: {e}")
            return False

    async def get_task(self, task_id: str) -> AgentResult | None:
        """从Redis获取任务状态"""
        if not self.redis_client:
            logger.warning(f"Redis not available, cannot retrieve task {task_id}")
            return None

        try:
            key = f"{self.task_prefix}{task_id}"
            data = await self.redis_client.get(key)

            if data:
                result = self._deserialize_result(data)
                logger.info(f"Task {task_id} retrieved from Redis")
                return result
            else:
                logger.warning(f"Task {task_id} not found in Redis")
                return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    async def update_task_status(
        self, task_id: str, status: AgentStatus, error: str | None = None
    ) -> bool:
        """更新任务状态"""
        if not self.redis_client:
            return False

        try:
            # 获取现有任务
            result = await self.get_task(task_id)
            if not result:
                logger.warning(f"Task {task_id} not found, cannot update status")
                return False

            # 更新状态
            result.status = status
            if error:
                result.error = error
            if status in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
                result.completed_at = datetime.utcnow()

            # 保存更新后的任务
            return await self.save_task(result)
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            return False

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if not self.redis_client:
            return False

        try:
            key = f"{self.task_prefix}{task_id}"

            # 删除任务数据
            await self.redis_client.delete(key)

            # 从任务列表中移除
            await self.redis_client.zrem(self.task_list_key, task_id)

            logger.info(f"Task {task_id} deleted from Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False

    async def list_tasks(
        self, limit: int = 100, offset: int = 0, status: AgentStatus | None = None
    ) -> list[AgentResult]:
        """列出任务（按创建时间倒序）"""
        if not self.redis_client:
            return []

        try:
            # 从任务列表中获取task_id（按时间戳倒序）
            task_ids = await self.redis_client.zrevrange(
                self.task_list_key, offset, offset + limit - 1
            )

            # 获取任务详情
            results = []
            for task_id in task_ids:
                result = await self.get_task(task_id)
                if result:
                    # 如果指定了状态过滤
                    if status is None or result.status == status:
                        results.append(result)

            logger.info(f"Retrieved {len(results)} tasks from Redis")
            return results
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    async def get_task_stats(self) -> dict:
        """获取任务统计信息"""
        if not self.redis_client:
            return {"total_tasks": 0, "redis_available": False}

        try:
            # 获取任务总数
            total_tasks = await self.redis_client.zcard(self.task_list_key)

            # 获取所有任务ID
            task_ids = await self.redis_client.zrange(self.task_list_key, 0, -1)

            # 统计各状态数量
            status_counts = {"running": 0, "completed": 0, "failed": 0, "pending": 0}

            for task_id in task_ids:
                result = await self.get_task(task_id)
                if result:
                    status_key = (
                        result.status.value
                        if hasattr(result.status, "value")
                        else str(result.status).lower()
                    )
                    if status_key in status_counts:
                        status_counts[status_key] += 1

            return {
                "total_tasks": total_tasks,
                "status_counts": status_counts,
                "redis_available": True,
            }
        except Exception as e:
            logger.error(f"Failed to get task stats: {e}")
            return {"total_tasks": 0, "redis_available": False, "error": str(e)}

    async def cleanup_old_tasks(self, days: int = 7) -> int:
        """清理旧任务（超过指定天数）"""
        if not self.redis_client:
            return 0

        try:
            import time

            cutoff_timestamp = time.time() - (days * 86400)

            # 获取过期的任务ID
            old_task_ids = await self.redis_client.zrangebyscore(
                self.task_list_key, 0, cutoff_timestamp
            )

            # 删除这些任务
            deleted_count = 0
            for task_id in old_task_ids:
                if await self.delete_task(task_id):
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} old tasks")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0


# 全局实例
task_manager = TaskManager()
