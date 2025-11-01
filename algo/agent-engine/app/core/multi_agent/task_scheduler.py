"""
Multi-Agent Task Scheduler - 智能任务调度器

实现功能：
- 任务优先级队列
- Agent能力匹配
- 负载均衡
- 智能任务分配
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""

    CRITICAL = 10  # 紧急
    HIGH = 8
    MEDIUM = 5
    LOW = 3
    BACKGROUND = 1


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务"""

    task_id: str
    description: str
    priority: TaskPriority
    required_capabilities: list[str]  # 需要的能力
    estimated_time: float  # 预估时间（秒）
    created_at: datetime
    deadline: datetime | None = None
    metadata: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str | None = None


@dataclass
class AgentCapabilityProfile:
    """Agent能力画像"""

    agent_id: str
    capabilities: dict[str, float]  # 能力名 -> 熟练度 (0-1)
    current_load: float  # 当前负载 (0-1)
    success_rate: float  # 历史成功率
    avg_response_time: float  # 平均响应时间（秒）
    last_updated: datetime


class SchedulingConstraints:
    """调度约束"""

    def __init__(
        self, max_parallel: int = 5, max_load_per_agent: float = 0.8, prefer_balanced: bool = True
    ):
        self.max_parallel = max_parallel
        self.max_load_per_agent = max_load_per_agent
        self.prefer_balanced = prefer_balanced


class Schedule:
    """调度计划"""

    def __init__(
        self,
        assignments: dict[str, str],  # task_id -> agent_id
        estimated_time: float,
        quality_score: float,
    ):
        self.assignments = assignments
        self.estimated_time = estimated_time
        self.quality_score = quality_score


class MultiAgentTaskScheduler:
    """
    Multi-Agent任务调度器

    用法:
        scheduler = MultiAgentTaskScheduler()

        # 注册Agent能力
        scheduler.register_agent_profile(AgentCapabilityProfile(
            agent_id="researcher_01",
            capabilities={"research": 0.9, "analysis": 0.8},
            current_load=0.3,
            success_rate=0.95,
            avg_response_time=2.5
        ))

        # 添加任务
        scheduler.add_task(Task(
            task_id="task_001",
            description="市场调研",
            priority=TaskPriority.HIGH,
            required_capabilities=["research"],
            estimated_time=300
        ))

        # 调度任务
        schedule = await scheduler.schedule_tasks(
            constraints=SchedulingConstraints(max_parallel=3)
        )
    """

    def __init__(self):
        # 任务队列（按优先级排序）
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.tasks: dict[str, Task] = {}

        # Agent能力画像
        self.agent_profiles: dict[str, AgentCapabilityProfile] = {}

        # 运行中的任务
        self.running_tasks: dict[str, str] = {}  # task_id -> agent_id

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "scheduled_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_scheduling_time": 0.0,
        }

        logger.info("MultiAgentTaskScheduler initialized")

    def register_agent_profile(self, profile: AgentCapabilityProfile):
        """注册Agent能力画像"""
        self.agent_profiles[profile.agent_id] = profile
        logger.info(f"Registered agent profile: {profile.agent_id}")

    def update_agent_load(self, agent_id: str, load: float):
        """更新Agent负载"""
        if agent_id in self.agent_profiles:
            self.agent_profiles[agent_id].current_load = load

    async def add_task(self, task: Task):
        """添加任务到队列"""
        self.tasks[task.task_id] = task
        self.stats["total_tasks"] += 1

        # 使用负优先级（数值越大，优先级越高）
        await self.task_queue.put((-task.priority.value, task.task_id))

        logger.info(f"Added task {task.task_id} with priority {task.priority.value}")

    async def schedule_tasks(self, constraints: SchedulingConstraints | None = None) -> Schedule:
        """
        调度所有待处理任务

        Args:
            constraints: 调度约束

        Returns:
            Schedule: 调度计划
        """
        if constraints is None:
            constraints = SchedulingConstraints()

        import time

        start_time = time.time()

        assignments = {}
        estimated_total_time = 0.0

        # 1. 收集待调度任务
        pending_tasks = [task for task in self.tasks.values() if task.status == TaskStatus.PENDING]

        # 2. 按优先级排序
        pending_tasks.sort(key=lambda t: t.priority.value, reverse=True)

        # 3. 为每个任务分配最合适的Agent
        for task in pending_tasks[: constraints.max_parallel]:
            best_agent = await self._find_best_agent(task, constraints)

            if best_agent:
                assignments[task.task_id] = best_agent.agent_id
                task.status = TaskStatus.ASSIGNED
                task.assigned_agent = best_agent.agent_id

                # 更新负载
                best_agent.current_load += task.estimated_time / 3600.0  # 转换为小时

                estimated_total_time = max(estimated_total_time, task.estimated_time)

                logger.info(f"Assigned task {task.task_id} to agent {best_agent.agent_id}")

        # 4. 计算调度质量评分
        quality_score = self._calculate_quality_score(assignments, pending_tasks)

        # 5. 更新统计
        self.stats["scheduled_tasks"] += len(assignments)
        scheduling_time = time.time() - start_time
        self.stats["avg_scheduling_time"] = (
            self.stats["avg_scheduling_time"] * (self.stats["scheduled_tasks"] - len(assignments))
            + scheduling_time
        ) / self.stats["scheduled_tasks"]

        logger.info(
            f"Scheduled {len(assignments)} tasks in {scheduling_time:.3f}s, "
            f"quality score: {quality_score:.2f}"
        )

        return Schedule(
            assignments=assignments,
            estimated_time=estimated_total_time,
            quality_score=quality_score,
        )

    async def _find_best_agent(
        self, task: Task, constraints: SchedulingConstraints
    ) -> AgentCapabilityProfile | None:
        """
        为任务找到最合适的Agent

        考虑因素：
        - 能力匹配度
        - 当前负载
        - 历史成功率
        - 响应时间
        """
        candidates = []

        for agent in self.agent_profiles.values():
            # 1. 检查负载约束
            if agent.current_load >= constraints.max_load_per_agent:
                continue

            # 2. 计算能力匹配度
            capability_score = self._calculate_capability_match(
                task.required_capabilities, agent.capabilities
            )

            if capability_score == 0:
                continue  # 没有所需能力

            # 3. 计算综合评分
            # 综合考虑：能力匹配(40%) + 成功率(30%) + 负载(20%) + 响应时间(10%)
            score = (
                capability_score * 0.4
                + agent.success_rate * 0.3
                + (1 - agent.current_load) * 0.2
                + (1 - min(agent.avg_response_time / 10, 1.0)) * 0.1
            )

            candidates.append((score, agent))

        if not candidates:
            logger.warning(f"No suitable agent found for task {task.task_id}")
            return None

        # 4. 选择评分最高的Agent
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_agent = candidates[0]

        logger.debug(
            f"Selected agent {best_agent.agent_id} for task {task.task_id} "
            f"(score: {best_score:.3f})"
        )

        return best_agent

    def _calculate_capability_match(
        self, required: list[str], available: dict[str, float]
    ) -> float:
        """计算能力匹配度"""
        if not required:
            return 1.0

        matched_scores = []
        for capability in required:
            if capability in available:
                matched_scores.append(available[capability])
            else:
                return 0.0  # 缺少必需能力

        # 返回平均熟练度
        return sum(matched_scores) / len(matched_scores)

    def _calculate_quality_score(self, assignments: dict[str, str], tasks: list[Task]) -> float:
        """计算调度质量评分"""
        if not assignments:
            return 0.0

        # 评分因素：
        # 1. 任务分配率
        assignment_rate = len(assignments) / len(tasks) if tasks else 0

        # 2. 负载均衡度
        agent_loads = {}
        for agent_id in assignments.values():
            agent_loads[agent_id] = agent_loads.get(agent_id, 0) + 1

        if len(agent_loads) > 1:
            loads = list(agent_loads.values())
            avg_load = sum(loads) / len(loads)
            variance = sum((l - avg_load) ** 2 for l in loads) / len(loads)  # noqa: E741
            balance_score = 1.0 / (1.0 + variance)
        else:
            balance_score = 1.0

        # 3. 高优先级任务完成度
        high_priority_assigned = sum(
            1
            for task_id in assignments
            if self.tasks[task_id].priority.value >= TaskPriority.HIGH.value
        )
        high_priority_total = sum(
            1 for task in tasks if task.priority.value >= TaskPriority.HIGH.value
        )
        priority_score = (
            high_priority_assigned / high_priority_total if high_priority_total > 0 else 1.0
        )

        # 综合评分
        quality_score = assignment_rate * 0.5 + balance_score * 0.3 + priority_score * 0.2

        return quality_score

    async def mark_task_completed(self, task_id: str, success: bool):
        """标记任务完成"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

        # 更新统计
        if success:
            self.stats["completed_tasks"] += 1
        else:
            self.stats["failed_tasks"] += 1

        # 更新Agent画像
        if task.assigned_agent and task.assigned_agent in self.agent_profiles:
            agent = self.agent_profiles[task.assigned_agent]

            # 更新成功率
            total_tasks = self.stats["completed_tasks"] + self.stats["failed_tasks"]
            agent.success_rate = (
                agent.success_rate * (total_tasks - 1) + (1.0 if success else 0.0)
            ) / total_tasks

            # 释放负载
            agent.current_load = max(0, agent.current_load - task.estimated_time / 3600.0)

        logger.info(f"Task {task_id} marked as {'completed' if success else 'failed'}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "pending_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
            ),
            "running_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS]
            ),
            "success_rate": (
                self.stats["completed_tasks"]
                / (self.stats["completed_tasks"] + self.stats["failed_tasks"])
                if (self.stats["completed_tasks"] + self.stats["failed_tasks"]) > 0
                else 0.0
            ),
        }
