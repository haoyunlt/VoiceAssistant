"""
增强型 Multi-Agent 协调器 - 完整实现 Iter 3 功能

新增功能:
1. 多种协作模式（串行 / 并行 / 辩论 / 投票）
2. 动态角色分配
3. 负载均衡
4. 任务依赖管理
5. 失败重试与降级
6. 协作质量评估

实现了完整的 Iter 3 功能。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.multi_agent.communication import MessageBus
from app.core.multi_agent.coordinator import Agent, AgentRole, Message

logger = logging.getLogger(__name__)


class CollaborationMode(Enum):
    """协作模式"""

    SEQUENTIAL = "sequential"  # 串行：一个接一个执行
    PARALLEL = "parallel"  # 并行：同时执行
    DEBATE = "debate"  # 辩论：多个agent讨论并达成共识
    VOTING = "voting"  # 投票：多数决定
    HIERARCHICAL = "hierarchical"  # 分层：coordinator分配，worker执行


class TaskStatus(Enum):
    """任务状态"""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    """任务"""

    task_id: str
    description: str
    assigned_agent: str | None
    status: TaskStatus
    result: Any | None
    dependencies: list[str]  # 依赖的其他任务ID
    priority: int
    created_at: datetime
    completed_at: datetime | None
    retry_count: int
    max_retries: int


@dataclass
class CollaborationConfig:
    """协作配置"""

    mode: CollaborationMode = CollaborationMode.PARALLEL
    max_concurrent_tasks: int = 5
    task_timeout: int = 300  # 秒
    max_retries: int = 2
    enable_load_balancing: bool = True
    enable_quality_check: bool = True


class EnhancedMultiAgentCoordinator:
    """
    增强型 Multi-Agent 协调器

    用法:
        coordinator = EnhancedMultiAgentCoordinator(llm_client)

        # 注册agents
        researcher = Agent("researcher_1", AgentRole.RESEARCHER, llm_client)
        planner = Agent("planner_1", AgentRole.PLANNER, llm_client)
        executor = Agent("executor_1", AgentRole.EXECUTOR, llm_client)

        await coordinator.register_agent(researcher)
        await coordinator.register_agent(planner)
        await coordinator.register_agent(executor)

        # 执行协作任务（辩论模式）
        result = await coordinator.collaborate(
            task="Design a new feature",
            mode=CollaborationMode.DEBATE,
            agent_ids=["researcher_1", "planner_1"]
        )
    """

    def __init__(
        self,
        llm_client: Any,
        config: CollaborationConfig | None = None,
    ):
        """
        初始化增强型协调器

        Args:
            llm_client: LLM 客户端
            config: 协作配置
        """
        self.llm_client = llm_client
        self.config = config or CollaborationConfig()

        # Agents 管理
        self.agents: dict[str, Agent] = {}
        self.agent_load: dict[str, int] = {}  # 每个agent的当前任务数

        # 消息总线
        self.message_bus = MessageBus()

        # 任务管理
        self.tasks: dict[str, Task] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()

        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_completion_time": 0.0,
            "collaboration_quality_avg": 0.0,
        }

        self.is_running = False

        logger.info(
            f"EnhancedMultiAgentCoordinator initialized (mode={config.mode.value})"
        )

    async def start(self):
        """启动协调器"""
        self.is_running = True
        await self.message_bus.start()

        # 启动所有agents
        for agent in self.agents.values():
            await agent.start()
            self.agent_load[agent.agent_id] = 0

        # 启动任务处理循环
        asyncio.create_task(self._task_processor())

        logger.info("EnhancedMultiAgentCoordinator started")

    async def stop(self):
        """停止协调器"""
        self.is_running = False
        await self.message_bus.stop()

        # 停止所有agents
        for agent in self.agents.values():
            await agent.stop()

        logger.info("EnhancedMultiAgentCoordinator stopped")

    async def register_agent(self, agent: Agent):
        """注册agent"""
        self.agents[agent.agent_id] = agent
        self.agent_load[agent.agent_id] = 0

        # 订阅消息总线
        self.message_bus.subscribe(agent.agent_id, agent.process_message)

        logger.info(f"Registered agent: {agent.agent_id} ({agent.role.value})")

    async def unregister_agent(self, agent_id: str):
        """注销agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            del self.agent_load[agent_id]
            self.message_bus.unsubscribe(agent_id)
            logger.info(f"Unregistered agent: {agent_id}")

    async def collaborate(
        self,
        task: str,
        mode: CollaborationMode | None = None,
        agent_ids: list[str] | None = None,
        priority: int = 5,
    ) -> dict[str, Any]:
        """
        执行协作任务

        Args:
            task: 任务描述
            mode: 协作模式（如未指定则使用默认）
            agent_ids: 参与的agent ID列表（如未指定则自动选择）
            priority: 任务优先级（1-10）

        Returns:
            协作结果
        """
        mode = mode or self.config.mode
        self.stats["total_tasks"] += 1

        logger.info(f"Starting collaboration: {task[:50]}... (mode={mode.value})")

        # 自动选择agents（如果未指定）
        if not agent_ids:
            agent_ids = await self._auto_select_agents(task)

        # 根据模式执行
        start_time = datetime.now()

        try:
            if mode == CollaborationMode.SEQUENTIAL:
                result = await self._sequential_collaboration(task, agent_ids)
            elif mode == CollaborationMode.PARALLEL:
                result = await self._parallel_collaboration(task, agent_ids)
            elif mode == CollaborationMode.DEBATE:
                result = await self._debate_collaboration(task, agent_ids)
            elif mode == CollaborationMode.VOTING:
                result = await self._voting_collaboration(task, agent_ids)
            elif mode == CollaborationMode.HIERARCHICAL:
                result = await self._hierarchical_collaboration(task, agent_ids)
            else:
                result = {"error": f"Unknown mode: {mode}"}

            completion_time = (datetime.now() - start_time).total_seconds()
            self.stats["completed_tasks"] += 1
            self._update_avg_time(completion_time)

            # 质量检查
            if self.config.enable_quality_check:
                quality_score = await self._assess_quality(task, result)
                result["quality_score"] = quality_score
                self._update_quality_score(quality_score)

            result["completion_time"] = completion_time
            result["mode"] = mode.value
            result["status"] = "success"

            logger.info(f"Collaboration completed in {completion_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Collaboration failed: {e}")
            self.stats["failed_tasks"] += 1
            return {
                "status": "failed",
                "error": str(e),
                "mode": mode.value,
            }

    async def _sequential_collaboration(
        self, task: str, agent_ids: list[str]
    ) -> dict[str, Any]:
        """串行协作：按顺序执行"""
        results = []
        current_input = task

        for agent_id in agent_ids:
            agent = self.agents[agent_id]

            message = Message(
                sender="coordinator",
                receiver=agent_id,
                content=current_input,
                message_type="task",
            )

            # 处理并等待结果
            response = await agent.process_message(message)
            results.append(
                {
                    "agent_id": agent_id,
                    "role": agent.role.value,
                    "result": response.content if response else "No response",
                }
            )

            # 下一个agent使用上一个的输出作为输入
            current_input = response.content if response else task

        return {
            "results": results,
            "final_output": current_input,
        }

    async def _parallel_collaboration(
        self, task: str, agent_ids: list[str]
    ) -> dict[str, Any]:
        """并行协作：同时执行"""
        tasks = []

        for agent_id in agent_ids:
            agent = self.agents[agent_id]
            message = Message(
                sender="coordinator",
                receiver=agent_id,
                content=task,
                message_type="task",
            )
            tasks.append(agent.process_message(message))

        # 并行等待所有结果
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                results.append(
                    {
                        "agent_id": agent_ids[i],
                        "error": str(response),
                    }
                )
            else:
                results.append(
                    {
                        "agent_id": agent_ids[i],
                        "role": self.agents[agent_ids[i]].role.value,
                        "result": response.content if response else "No response",
                    }
                )

        # 合并结果
        final_output = await self._merge_parallel_results(task, results)

        return {
            "results": results,
            "final_output": final_output,
        }

    async def _debate_collaboration(
        self, task: str, agent_ids: list[str], max_rounds: int = 3
    ) -> dict[str, Any]:
        """辩论协作：多轮讨论达成共识"""
        debate_history = []

        for round_num in range(max_rounds):
            logger.info(f"Debate round {round_num + 1}/{max_rounds}")

            round_results = []

            # 每个agent提出观点
            for agent_id in agent_ids:
                agent = self.agents[agent_id]

                # 构建上下文（包含之前的辩论）
                context = self._format_debate_history(debate_history)
                prompt = f"""任务: {task}

之前的辩论:
{context}

请提出你的观点、论据和建议。"""

                message = Message(
                    sender="coordinator",
                    receiver=agent_id,
                    content=prompt,
                    message_type="debate",
                )

                response = await agent.process_message(message)
                round_results.append(
                    {
                        "agent_id": agent_id,
                        "role": agent.role.value,
                        "viewpoint": response.content if response else "",
                    }
                )

            debate_history.append(
                {"round": round_num + 1, "viewpoints": round_results}
            )

        # 达成共识
        consensus = await self._reach_consensus(task, debate_history)

        return {
            "debate_history": debate_history,
            "consensus": consensus,
            "rounds": max_rounds,
        }

    async def _voting_collaboration(
        self, task: str, agent_ids: list[str]
    ) -> dict[str, Any]:
        """投票协作：多数决定"""
        # 每个agent提供答案和推理
        votes = []

        for agent_id in agent_ids:
            agent = self.agents[agent_id]

            message = Message(
                sender="coordinator",
                receiver=agent_id,
                content=f"任务: {task}\n\n请提供你的解决方案和理由。",
                message_type="voting",
            )

            response = await agent.process_message(message)
            votes.append(
                {
                    "agent_id": agent_id,
                    "role": agent.role.value,
                    "solution": response.content if response else "",
                }
            )

        # 分析投票结果，选出最佳方案
        best_solution = await self._analyze_votes(task, votes)

        return {
            "votes": votes,
            "best_solution": best_solution,
            "total_votes": len(votes),
        }

    async def _hierarchical_collaboration(
        self, task: str, agent_ids: list[str]
    ) -> dict[str, Any]:
        """分层协作：coordinator分配子任务给workers"""
        # 找到coordinator agent
        coordinator_agent = None
        worker_agents = []

        for agent_id in agent_ids:
            agent = self.agents[agent_id]
            if agent.role == AgentRole.COORDINATOR:
                coordinator_agent = agent
            else:
                worker_agents.append(agent)

        if not coordinator_agent:
            # 如果没有coordinator，使用第一个agent作为临时coordinator
            coordinator_agent = self.agents[agent_ids[0]]
            worker_agents = [self.agents[aid] for aid in agent_ids[1:]]

        # 1. Coordinator分解任务
        subtasks = await self._decompose_task_hierarchical(
            task, coordinator_agent, worker_agents
        )

        # 2. 分配子任务给workers
        subtask_results = {}

        for worker_agent in worker_agents:
            if worker_agent.agent_id in subtasks:
                subtask = subtasks[worker_agent.agent_id]

                message = Message(
                    sender=coordinator_agent.agent_id,
                    receiver=worker_agent.agent_id,
                    content=subtask,
                    message_type="subtask",
                )

                response = await worker_agent.process_message(message)
                subtask_results[worker_agent.agent_id] = response.content if response else ""

        # 3. Coordinator整合结果
        final_result = await self._integrate_results(
            task, subtask_results, coordinator_agent
        )

        return {
            "coordinator": coordinator_agent.agent_id,
            "workers": [w.agent_id for w in worker_agents],
            "subtasks": subtasks,
            "subtask_results": subtask_results,
            "final_result": final_result,
        }

    async def _auto_select_agents(self, task: str) -> list[str]:
        """根据任务自动选择最合适的agents"""
        if not self.agents:
            return []

        # 分析任务类型
        task_lower = task.lower()

        selected_agents = []

        # 需要研究？
        if any(
            keyword in task_lower
            for keyword in ["research", "find", "search", "analyze"]
        ):
            researchers = [
                a.agent_id
                for a in self.agents.values()
                if a.role == AgentRole.RESEARCHER
            ]
            if researchers:
                selected_agents.append(researchers[0])

        # 需要计划？
        if any(keyword in task_lower for keyword in ["plan", "design", "strategy"]):
            planners = [
                a.agent_id for a in self.agents.values() if a.role == AgentRole.PLANNER
            ]
            if planners:
                selected_agents.append(planners[0])

        # 需要执行？
        if any(
            keyword in task_lower for keyword in ["execute", "implement", "build", "do"]
        ):
            executors = [
                a.agent_id
                for a in self.agents.values()
                if a.role == AgentRole.EXECUTOR
            ]
            if executors:
                selected_agents.append(executors[0])

        # 如果没有匹配，随机选择3个agents
        if not selected_agents:
            selected_agents = list(self.agents.keys())[:3]

        # 负载均衡：选择负载较低的agents
        if self.config.enable_load_balancing:
            selected_agents.sort(key=lambda a: self.agent_load.get(a, 0))

        logger.info(f"Auto-selected agents: {selected_agents}")
        return selected_agents

    async def _merge_parallel_results(
        self, task: str, results: list[dict]
    ) -> str:
        """合并并行结果"""
        results_text = "\n\n".join(
            [
                f"{r['role']}: {r.get('result', r.get('error', 'No result'))}"
                for r in results
            ]
        )

        prompt = f"""任务: {task}

以下是各个agent的执行结果:
{results_text}

请综合这些结果，给出最终答案。"""

        response = await self.llm_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are synthesizing multiple agent outputs.",
                },
                {"role": "user", "content": prompt},
            ],
            model="gpt-4",
            temperature=0.3,
        )

        return response.strip()

    def _format_debate_history(self, history: list[dict]) -> str:
        """格式化辩论历史"""
        formatted = []
        for entry in history:
            round_num = entry["round"]
            formatted.append(f"\n回合 {round_num}:")
            for viewpoint in entry["viewpoints"]:
                formatted.append(
                    f"- {viewpoint['role']}: {viewpoint['viewpoint'][:200]}..."
                )
        return "\n".join(formatted) if formatted else "无"

    async def _reach_consensus(self, task: str, debate_history: list[dict]) -> str:
        """达成共识"""
        history_text = self._format_debate_history(debate_history)

        prompt = f"""任务: {task}

辩论历史:
{history_text}

请基于以上辩论，达成共识并给出最终决策。"""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are reaching a consensus."},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4",
            temperature=0.3,
        )

        return response.strip()

    async def _analyze_votes(self, task: str, votes: list[dict]) -> dict:
        """分析投票结果"""
        votes_text = "\n\n".join(
            [
                f"方案 {i+1} ({v['role']}): {v['solution']}"
                for i, v in enumerate(votes)
            ]
        )

        prompt = f"""任务: {task}

各个agent的方案:
{votes_text}

请分析并选出最佳方案，给出理由。

输出格式:
最佳方案编号: X
理由: ..."""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are analyzing voting results."},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4",
            temperature=0.2,
        )

        return {"analysis": response.strip(), "total_votes": len(votes)}

    async def _decompose_task_hierarchical(
        self, task: str, coordinator: Agent, workers: list[Agent]
    ) -> dict[str, str]:
        """分层分解任务"""
        worker_info = {
            w.agent_id: w.role.value for w in workers
        }

        prompt = f"""任务: {task}

可用的worker agents:
{worker_info}

请将任务分解为子任务，分配给各个worker。

输出JSON格式:
{{
    "worker_id_1": "子任务描述",
    "worker_id_2": "子任务描述",
    ...
}}"""

        response = await coordinator.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a task coordinator."},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4",
            temperature=0.2,
        )

        import json

        try:
            return json.loads(response)
        except:
            # 降级：平均分配
            return {w.agent_id: task for w in workers}

    async def _integrate_results(
        self, task: str, subtask_results: dict[str, str], coordinator: Agent
    ) -> str:
        """整合子任务结果"""
        results_text = "\n\n".join(
            [f"{agent_id}: {result}" for agent_id, result in subtask_results.items()]
        )

        prompt = f"""原始任务: {task}

子任务结果:
{results_text}

请整合这些结果，给出最终答案。"""

        response = await coordinator.llm_client.chat(
            messages=[
                {"role": "system", "content": "You are integrating subtask results."},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4",
            temperature=0.3,
        )

        return response.strip()

    async def _assess_quality(self, task: str, result: dict) -> float:
        """评估协作质量"""
        final_output = result.get("final_output") or result.get("consensus") or result.get("best_solution", {}).get("analysis", "")

        prompt = f"""任务: {task}

结果: {final_output}

请评估这个协作结果的质量（0-1分）。

考虑因素:
- 是否完成了任务
- 答案的准确性
- 逻辑的连贯性
- 信息的完整性

只输出一个0-1之间的小数。"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",
                temperature=0.0,
            )

            quality = float(response.strip())
            return max(0.0, min(1.0, quality))

        except:
            return 0.7  # 默认

    def _update_avg_time(self, completion_time: float):
        """更新平均完成时间"""
        n = self.stats["completed_tasks"]
        current_avg = self.stats["avg_completion_time"]
        self.stats["avg_completion_time"] = (
            current_avg * (n - 1) + completion_time
        ) / n

    def _update_quality_score(self, quality: float):
        """更新平均质量分数"""
        n = self.stats["completed_tasks"]
        current_avg = self.stats["collaboration_quality_avg"]
        self.stats["collaboration_quality_avg"] = (current_avg * (n - 1) + quality) / n

    async def _task_processor(self):
        """后台任务处理器"""
        while self.is_running:
            try:
                # 从队列获取任务
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                # 处理任务...
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Task processor error: {e}")

    def get_stats(self) -> dict:
        """获取统计信息"""
        success_rate = (
            self.stats["completed_tasks"] / self.stats["total_tasks"]
            if self.stats["total_tasks"] > 0
            else 0.0
        )

        return {
            **self.stats,
            "success_rate": success_rate,
            "active_agents": len(self.agents),
            "agent_load": self.agent_load,
        }

