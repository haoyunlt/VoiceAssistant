"""多Agent协作执行器"""
import asyncio
import json
import logging
from typing import Any

from app.infrastructure.llm_client import LLMClient
from app.infrastructure.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentRole:
    """Agent角色定义"""

    def __init__(
        self,
        role_id: str,
        name: str,
        description: str,
        capabilities: list[str],
        tools: list[str]
    ):
        self.role_id = role_id
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.tools = tools


class Message:
    """Agent间消息"""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        message_type: str = "task",
        metadata: dict | None = None
    ):
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.content = content
        self.message_type = message_type
        self.metadata = metadata or {}
        import time
        self.timestamp = time.time()


class MultiAgentExecutor:
    """
    多Agent协作执行器

    支持的协作模式：
    1. 顺序协作：Agent按顺序完成子任务
    2. 并行协作：多个Agent并行处理任务
    3. 层级协作：主Agent协调多个子Agent
    4. 讨论协作：多个Agent讨论得出结论
    """

    def __init__(self, llm_client: LLMClient, tool_registry: ToolRegistry) -> None:
        """
        初始化多Agent执行器

        Args:
            llm_client: LLM客户端
            tool_registry: 工具注册表
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.agents: dict[str, AgentRole] = {}
        self.message_queue: list[Message] = []

    def register_agent(self, agent: AgentRole) -> None:
        """注册Agent"""
        self.agents[agent.role_id] = agent
        logger.info(f"Registered agent: {agent.name} ({agent.role_id})")

    async def execute_sequential(
        self,
        task: str,
        agent_sequence: list[str],
        context: str | None = None
    ) -> dict[str, Any]:
        """
        顺序协作模式：Agent按顺序完成任务

        Args:
            task: 总任务描述
            agent_sequence: Agent ID的执行顺序
            context: 上下文信息

        Returns:
            执行结果
        """
        logger.info(f"Starting sequential multi-agent execution: {len(agent_sequence)} agents")

        results = []
        accumulated_output = ""

        for i, agent_id in enumerate(agent_sequence):
            agent = self.agents.get(agent_id)
            if not agent:
                logger.warning(f"Agent not found: {agent_id}")
                continue

            logger.info(f"Step {i+1}/{len(agent_sequence)}: {agent.name}")

            # 构建子任务
            sub_task = await self._decompose_task(task, agent, i, len(agent_sequence))

            # 执行子任务
            sub_result = await self._execute_agent_task(
                agent=agent,
                task=sub_task,
                context=f"{context}\n\nPrevious results:\n{accumulated_output}" if accumulated_output else context
            )

            results.append({
                "agent": agent.name,
                "agent_id": agent_id,
                "step": i + 1,
                "task": sub_task,
                "result": sub_result
            })

            accumulated_output += f"\n[{agent.name}]: {sub_result}\n"

        # 综合最终答案
        final_answer = await self._synthesize_results(task, results)

        return {
            "task": task,
            "mode": "sequential",
            "agents_involved": len(agent_sequence),
            "steps": results,
            "final_answer": final_answer
        }

    async def execute_parallel(
        self,
        task: str,
        agent_ids: list[str],
        context: str | None = None
    ) -> dict[str, Any]:
        """
        并行协作模式：多个Agent同时处理任务

        Args:
            task: 任务描述
            agent_ids: 参与的Agent ID列表
            context: 上下文信息

        Returns:
            执行结果
        """
        logger.info(f"Starting parallel multi-agent execution: {len(agent_ids)} agents")

        # 创建并行任务
        tasks_to_run = []
        for agent_id in agent_ids:
            agent = self.agents.get(agent_id)
            if not agent:
                continue

            tasks_to_run.append(
                self._execute_agent_task(agent, task, context)
            )

        # 并行执行
        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

        # 整理结果
        agent_results = []
        for i, agent_id in enumerate(agent_ids):
            agent = self.agents.get(agent_id)
            if not agent:
                continue

            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Agent {agent.name} failed: {result}")
                result = f"Error: {str(result)}"

            agent_results.append({
                "agent": agent.name,
                "agent_id": agent_id,
                "result": result
            })

        # 综合答案
        final_answer = await self._synthesize_results(task, agent_results)

        return {
            "task": task,
            "mode": "parallel",
            "agents_involved": len(agent_ids),
            "agent_results": agent_results,
            "final_answer": final_answer
        }

    async def execute_hierarchical(
        self,
        task: str,
        coordinator_id: str,
        worker_ids: list[str],
        context: str | None = None
    ) -> dict[str, Any]:
        """
        层级协作模式：coordinator分配任务给workers

        Args:
            task: 任务描述
            coordinator_id: 协调者Agent ID
            worker_ids: 工作者Agent ID列表
            context: 上下文信息

        Returns:
            执行结果
        """
        logger.info("Starting hierarchical multi-agent execution")

        coordinator = self.agents.get(coordinator_id)
        if not coordinator:
            raise ValueError(f"Coordinator agent not found: {coordinator_id}")

        # 1. Coordinator分解任务
        subtasks = await self._coordinator_decompose(coordinator, task, worker_ids)

        # 2. 分配给workers并行执行
        worker_results = []
        tasks_to_run = []

        for subtask in subtasks:
            worker_id = subtask["assigned_to"]
            worker = self.agents.get(worker_id)
            if not worker:
                continue

            tasks_to_run.append(
                self._execute_agent_task(
                    agent=worker,
                    task=subtask["task"],
                    context=context
                )
            )

        results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

        # 整理workers结果
        for i, subtask in enumerate(subtasks):
            worker_id = subtask["assigned_to"]
            worker = self.agents.get(worker_id)
            if not worker:
                continue

            result = results[i]
            if isinstance(result, Exception):
                result = f"Error: {str(result)}"

            worker_results.append({
                "agent": worker.name,
                "agent_id": worker_id,
                "subtask": subtask["task"],
                "result": result
            })

        # 3. Coordinator综合结果
        final_answer = await self._coordinator_synthesize(
            coordinator=coordinator,
            task=task,
            worker_results=worker_results
        )

        return {
            "task": task,
            "mode": "hierarchical",
            "coordinator": coordinator.name,
            "workers": len(worker_ids),
            "subtasks": subtasks,
            "worker_results": worker_results,
            "final_answer": final_answer
        }

    async def execute_discussion(
        self,
        task: str,
        agent_ids: list[str],
        max_rounds: int = 3,
        context: str | None = None
    ) -> dict[str, Any]:
        """
        讨论协作模式：多个Agent讨论达成共识

        Args:
            task: 任务描述
            agent_ids: 参与讨论的Agent ID列表
            max_rounds: 最大讨论轮数
            context: 上下文信息

        Returns:
            执行结果
        """
        logger.info(f"Starting discussion multi-agent execution: {len(agent_ids)} agents, {max_rounds} rounds")

        discussion_history: list[dict[str, Any]] = []

        for round_num in range(max_rounds):
            logger.info(f"Discussion round {round_num + 1}/{max_rounds}")

            round_results = []

            for agent_id in agent_ids:
                agent = self.agents.get(agent_id)
                if not agent:
                    continue

                # 构建讨论prompt
                discussion_prompt = self._build_discussion_prompt(
                    task=task,
                    agent=agent,
                    discussion_history=discussion_history,
                    round_num=round_num,
                    context=context
                )

                # Agent发表观点
                opinion = await self.llm_client.generate(
                    prompt=discussion_prompt,
                    temperature=0.7,
                    max_tokens=500
                )

                round_results.append({
                    "agent": agent.name,
                    "agent_id": agent_id,
                    "opinion": opinion
                })

            discussion_history.append({
                "round": round_num + 1,
                "opinions": round_results
            })

            # 检查是否达成共识
            consensus = await self._check_consensus(round_results)
            if consensus["reached"]:
                logger.info(f"Consensus reached in round {round_num + 1}")
                return {
                    "task": task,
                    "mode": "discussion",
                    "agents_involved": len(agent_ids),
                    "rounds": round_num + 1,
                    "discussion_history": discussion_history,
                    "consensus": consensus["conclusion"]
                }

        # 未达成共识，由多数投票决定
        final_conclusion = await self._vote_conclusion(task, discussion_history)

        return {
            "task": task,
            "mode": "discussion",
            "agents_involved": len(agent_ids),
            "rounds": max_rounds,
            "discussion_history": discussion_history,
            "final_conclusion": final_conclusion,
            "consensus_reached": False
        }

    async def _decompose_task(
        self,
        task: str,
        agent: AgentRole,
        step: int,
        total_steps: int
    ) -> str:
        """为特定Agent分解子任务"""
        prompt = f"""Given the overall task and the agent's role, determine what specific subtask this agent should perform.

Overall Task: {task}

Agent Role: {agent.name}
Agent Description: {agent.description}
Agent Capabilities: {', '.join(agent.capabilities)}

This is step {step + 1} of {total_steps}.

What specific subtask should this agent perform? Be concise and actionable.

Subtask:"""

        subtask = await self.llm_client.generate(prompt=prompt, temperature=0.5, max_tokens=200)
        return subtask.strip()  # type: ignore

    async def _execute_agent_task(
        self,
        agent: AgentRole,
        task: str,
        context: str | None
    ) -> str:  # type: ignore
        """执行单个Agent的任务"""
        prompt_parts = [
            f"You are {agent.name}.",
            f"Role: {agent.description}",
            f"Capabilities: {', '.join(agent.capabilities)}",
            f"\nTask: {task}"
        ]

        if context:
            prompt_parts.insert(3, f"\nContext: {context}")

        prompt_parts.append("\nProvide your response:")

        prompt = "\n".join(prompt_parts)

        result = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=800
        )

        return result.strip()  # type: ignore

    async def _synthesize_results(self, task: str, results: list[dict[str, Any]]) -> str:  # type: ignore
        """综合多个Agent的结果"""
        results_text = "\n\n".join([
            f"[{r['agent']}]: {r.get('result', r.get('opinion', ''))}"
            for r in results
        ])

        prompt = f"""Synthesize the following agent results into a final comprehensive answer.

Original Task: {task}

Agent Results:
{results_text}

Provide a clear, comprehensive final answer:"""

        final_answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=800
        )

        return final_answer.strip()  # type: ignore

    async def _coordinator_decompose(
        self,
        coordinator: AgentRole,
        task: str,
        worker_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Coordinator分解任务"""
        workers_info = "\n".join([
            f"- {self.agents[wid].name}: {self.agents[wid].description}"
            for wid in worker_ids if wid in self.agents
        ])

        prompt = f"""As a coordinator, decompose the following task into subtasks for your team.

Task: {task}

Available Workers:
{workers_info}

Decompose this task into {len(worker_ids)} subtasks, one for each worker.
Respond in JSON format:
[
  {{"task": "subtask description", "assigned_to": "worker_id"}},
  ...
]
"""

        response = await self.llm_client.generate(prompt=prompt, temperature=0.5, max_tokens=500)

        try:
            subtasks = json.loads(response)
            return subtasks  # type: ignore
        except json.JSONDecodeError:
            # 如果解析失败，平均分配
            return [
                {"task": task, "assigned_to": wid}
                for wid in worker_ids
            ]

    async def _coordinator_synthesize(
        self,
        coordinator: AgentRole,
        task: str,
        worker_results: list[dict[str, Any]]
    ) -> str:
        """Coordinator综合workers的结果"""
        results_text = "\n\n".join([
            f"[{r['agent']} - {r['subtask']}]:\n{r['result']}"
            for r in worker_results
        ])

        prompt = f"""As a coordinator, synthesize your team's results into a final answer.

Original Task: {task}

Team Results:
{results_text}

Provide a comprehensive final answer:"""

        final_answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=800
        )

        return final_answer.strip()  # type: ignore

    def _build_discussion_prompt(
        self,
        task: str,
        agent: AgentRole,
        discussion_history: list[dict[str, Any]],
        round_num: int,
        context: str | None
    ) -> str:
        """构建讨论prompt"""
        prompt_parts = [
            f"You are {agent.name}, participating in a group discussion.",
            f"Your role: {agent.description}",
            f"\nDiscussion Topic: {task}"
        ]

        if context:
            prompt_parts.append(f"\nContext: {context}")

        if discussion_history:
            prompt_parts.append("\nPrevious Discussion:")
            for round_data in discussion_history:
                prompt_parts.append(f"\nRound {round_data['round']}:")
                for opinion in round_data['opinions']:
                    prompt_parts.append(f"  [{opinion['agent']}]: {opinion['opinion']}")

        prompt_parts.append(f"\nRound {round_num + 1} - Provide your perspective:")

        return "\n".join(prompt_parts)

    async def _check_consensus(self, opinions: list[dict[str, Any]]) -> dict[str, Any]:
        """检查是否达成共识"""
        opinions_text = "\n".join([
            f"[{op['agent']}]: {op['opinion']}"
            for op in opinions
        ])

        prompt = f"""Analyze if these opinions have reached consensus.

Opinions:
{opinions_text}

Have they reached consensus? Respond in JSON:
{{
    "reached": true/false,
    "conclusion": "summary if consensus reached"
}}
"""

        response = await self.llm_client.generate(prompt=prompt, temperature=0.3, max_tokens=200)

        try:
            result = json.loads(response)
            return result  # type: ignore
        except json.JSONDecodeError:
            return {"reached": False, "conclusion": ""}

    async def _vote_conclusion(self, task: str, discussion_history: list[dict[str, Any]]) -> str:  # type: ignore
        """通过投票得出结论"""
        all_opinions = []
        for round_data in discussion_history:
            all_opinions.extend(round_data['opinions'])

        opinions_text = "\n".join([
            f"[{op['agent']}]: {op['opinion']}"
            for op in all_opinions
        ])

        prompt = f"""Based on the discussion, determine the most supported conclusion.

Task: {task}

All Opinions:
{opinions_text}

What is the conclusion most agents agree on?"""

        conclusion = await self.llm_client.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=500
        )

        return conclusion.strip()  # type: ignore
