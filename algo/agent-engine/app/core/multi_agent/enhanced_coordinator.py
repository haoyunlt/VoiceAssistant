"""
Enhanced Multi-Agent Coordinator - 增强Multi-Agent协调器

集成功能：
- 去中心化通信
- Agent能力画像
- 增强冲突解决
- 智能任务调度
- 通信监控
"""

import asyncio
import logging
from typing import Any

from app.core.multi_agent.communication_monitor import get_communication_monitor
from app.core.multi_agent.coordinator import Agent, AgentRole, Message, MultiAgentCoordinator
from app.core.multi_agent.enhanced_conflict_resolver import (
    ConflictType,
    EnhancedConflictResolver,
)
from app.core.multi_agent.task_scheduler import (
    AgentCapabilityProfile,
    MultiAgentTaskScheduler,
    Task,
    TaskPriority,
)

logger = logging.getLogger(__name__)


class EnhancedMultiAgentCoordinator(MultiAgentCoordinator):
    """
    增强Multi-Agent协调器

    新增功能：
    - 集成冲突解决器
    - 集成任务调度器
    - 集成通信监控
    - Agent能力动态更新

    用法:
        coordinator = EnhancedMultiAgentCoordinator(llm_client, tool_registry)

        # 注册Agent
        await coordinator.register_agent_with_capabilities(
            agent=researcher_agent,
            capabilities={"research": 0.9, "analysis": 0.8}
        )

        # 执行协作任务（带任务调度）
        result = await coordinator.collaborate_with_scheduling(
            task="分析市场趋势",
            priority=TaskPriority.HIGH,
            required_capabilities=["research", "analysis"]
        )
    """

    def __init__(self, llm_client: Any, tool_registry: Any, config: dict | None = None):
        super().__init__()
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.config = config or {}

        # 初始化子组件
        self.conflict_resolver = EnhancedConflictResolver(
            llm_client=llm_client,
            coordinator=None,  # 将在注册coordinator agent后设置
        )

        self.task_scheduler = MultiAgentTaskScheduler()
        self.communication_monitor = get_communication_monitor()

        # Agent能力追踪
        self.agent_capabilities: dict[str, AgentCapabilityProfile] = {}

        logger.info("EnhancedMultiAgentCoordinator initialized")

    async def register_agent_with_capabilities(
        self,
        agent: Agent,
        capabilities: dict[str, float],
        success_rate: float = 0.5,
        avg_response_time: float = 2.0,
    ):
        """
        注册Agent并记录能力

        Args:
            agent: Agent对象
            capabilities: 能力字典 {能力名: 熟练度(0-1)}
            success_rate: 初始成功率
            avg_response_time: 平均响应时间
        """
        # 注册到父类
        self.register_agent(agent)

        # 创建能力画像
        from datetime import datetime

        profile = AgentCapabilityProfile(
            agent_id=agent.agent_id,
            capabilities=capabilities,
            current_load=0.0,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            last_updated=datetime.now(),
        )

        self.agent_capabilities[agent.agent_id] = profile
        self.task_scheduler.register_agent_profile(profile)

        # 如果是coordinator，设置到conflict_resolver
        if agent.role == AgentRole.COORDINATOR:
            self.conflict_resolver.coordinator = agent

        logger.info(
            f"Registered agent {agent.agent_id} with capabilities: {list(capabilities.keys())}"
        )

    async def collaborate_with_scheduling(
        self,
        task_description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        required_capabilities: list[str] | None = None,
        estimated_time: float = 300.0,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """
        带任务调度的协作执行

        Args:
            task_description: 任务描述
            priority: 任务优先级
            required_capabilities: 需要的能力
            estimated_time: 预估时间（秒）
            timeout: 超时时间

        Returns:
            执行结果
        """
        import time
        from datetime import datetime

        start_time = time.time()

        # 1. 创建任务
        task = Task(
            task_id=f"task_{datetime.now().timestamp()}",
            description=task_description,
            priority=priority,
            required_capabilities=required_capabilities or [],
            estimated_time=estimated_time,
            created_at=datetime.now(),
        )

        # 2. 添加到调度器
        await self.task_scheduler.add_task(task)

        # 3. 调度任务
        from app.core.multi_agent.task_scheduler import SchedulingConstraints

        schedule = await self.task_scheduler.schedule_tasks(
            constraints=SchedulingConstraints(max_parallel=len(self.agents))
        )

        if task.task_id not in schedule.assignments:
            logger.warning(f"Task {task.task_id} could not be scheduled")
            return {"success": False, "error": "No suitable agent found", "task": task_description}

        # 4. 获取分配的Agent
        assigned_agent_id = schedule.assignments[task.task_id]
        assigned_agent = self.agents.get(assigned_agent_id)

        if not assigned_agent:
            return {
                "success": False,
                "error": f"Agent {assigned_agent_id} not found",
                "task": task_description,
            }

        logger.info(f"Task {task.task_id} assigned to {assigned_agent_id}")

        # 5. 执行任务（通过消息传递）
        message = Message(
            sender="coordinator",
            receiver=assigned_agent_id,
            content=task_description,
            message_type="task",
            priority=priority.value,
            metadata={"task_id": task.task_id},
        )

        # 记录通信
        msg_id = self.communication_monitor.record_message_sent(
            from_agent="coordinator",
            to_agent=assigned_agent_id,
            message_type="task",
            content=task_description,
            metadata={"task_id": task.task_id},
        )

        # 发送消息到Agent
        await assigned_agent.message_queue.put(message)
        self.communication_monitor.record_message_received(msg_id)

        # 6. 等待响应
        try:
            async with asyncio.timeout(timeout):
                response = await assigned_agent.process_message(message)

                # 记录处理完成
                processing_time = time.time() - start_time
                self.communication_monitor.record_message_processed(msg_id, processing_time)

                # 更新任务状态
                await self.task_scheduler.mark_task_completed(task.task_id, success=True)

                # 更新Agent能力画像
                await self._update_agent_performance(
                    assigned_agent_id, success=True, response_time=processing_time
                )

                return {
                    "success": True,
                    "task": task_description,
                    "agent": assigned_agent_id,
                    "result": response.content if response else None,
                    "execution_time": processing_time,
                    "schedule_quality": schedule.quality_score,
                }

        except TimeoutError:
            logger.warning(f"Task {task.task_id} timed out")
            self.communication_monitor.record_message_failed(msg_id, "Timeout")
            await self.task_scheduler.mark_task_completed(task.task_id, success=False)

            return {
                "success": False,
                "error": "Task execution timeout",
                "task": task_description,
                "agent": assigned_agent_id,
            }

    async def resolve_agent_conflict(
        self, agent1_id: str, agent2_id: str, conflict_type: ConflictType, context: dict[str, Any]
    ) -> dict:
        """
        解决Agent间冲突

        Args:
            agent1_id: Agent1 ID
            agent2_id: Agent2 ID
            conflict_type: 冲突类型
            context: 上下文信息

        Returns:
            解决结果
        """
        agent1 = self.agents.get(agent1_id)
        agent2 = self.agents.get(agent2_id)

        if not agent1 or not agent2:
            return {"success": False, "error": "Agent not found"}

        # 使用冲突解决器
        resolution = await self.conflict_resolver.resolve_conflict(
            agent1=agent1, agent2=agent2, conflict_type=conflict_type, context=context
        )

        return {
            "success": True,
            "conflict_type": conflict_type.value,
            "strategy_used": resolution.strategy_used.value,
            "winner": resolution.winner.agent_id if resolution.winner else None,
            "decision": resolution.decision,
        }

    async def _update_agent_performance(self, agent_id: str, success: bool, response_time: float):
        """更新Agent性能指标"""
        if agent_id not in self.agent_capabilities:
            return

        profile = self.agent_capabilities[agent_id]

        # 更新成功率（指数移动平均）
        alpha = 0.1  # 平滑系数
        profile.success_rate = (
            alpha * (1.0 if success else 0.0) + (1 - alpha) * profile.success_rate
        )

        # 更新平均响应时间
        profile.avg_response_time = alpha * response_time + (1 - alpha) * profile.avg_response_time

        # 更新时间戳
        from datetime import datetime

        profile.last_updated = datetime.now()

        logger.debug(
            f"Updated {agent_id} performance: "
            f"success_rate={profile.success_rate:.2f}, "
            f"avg_response_time={profile.avg_response_time:.2f}s"
        )

    def get_agent_capabilities(self, agent_id: str) -> dict | None:
        """获取Agent能力画像"""
        profile = self.agent_capabilities.get(agent_id)
        if profile:
            return {
                "agent_id": profile.agent_id,
                "capabilities": profile.capabilities,
                "current_load": profile.current_load,
                "success_rate": profile.success_rate,
                "avg_response_time": profile.avg_response_time,
                "last_updated": profile.last_updated.isoformat(),
            }
        return None

    def get_communication_stats(self) -> dict:
        """获取通信统计"""
        return self.communication_monitor.get_stats()

    def get_scheduling_stats(self) -> dict:
        """获取调度统计"""
        return self.task_scheduler.get_stats()

    def get_conflict_stats(self) -> dict:
        """获取冲突解决统计"""
        return self.conflict_resolver.get_stats()

    def export_communication_graph(self) -> dict:
        """导出通信图（用于可视化）"""
        return self.communication_monitor.export_to_visualization()

    async def health_check(self) -> dict:
        """健康检查"""
        # 检测通信异常
        anomalies = self.communication_monitor.detect_communication_anomalies()

        # 统计信息
        comm_stats = self.get_communication_stats()
        sched_stats = self.get_scheduling_stats()
        conflict_stats = self.get_conflict_stats()

        # 判断健康状态
        is_healthy = (
            len(anomalies) == 0
            and comm_stats.get("failure_rate", 0) < 0.1
            and sched_stats.get("success_rate", 0) > 0.8
        )

        return {
            "healthy": is_healthy,
            "anomalies": anomalies,
            "communication": comm_stats,
            "scheduling": sched_stats,
            "conflict_resolution": conflict_stats,
            "total_agents": len(self.agents),
        }
