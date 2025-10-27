"""
Multi-Agent Coordinator
多 Agent 协调器，支持多个 Agent 协同完成复杂任务
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent 角色"""
    PLANNER = "planner"  # 规划者
    RESEARCHER = "researcher"  # 研究员
    WRITER = "writer"  # 写作者
    CRITIC = "critic"  # 批评者
    EXECUTOR = "executor"  # 执行者
    COORDINATOR = "coordinator"  # 协调者


@dataclass
class Agent:
    """Agent 定义"""
    name: str
    role: AgentRole
    capabilities: List[str]
    llm_model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class AgentMessage:
    """Agent 消息"""
    from_agent: str
    to_agent: str
    content: str
    message_type: str  # "request", "response", "broadcast"
    metadata: Dict = None


class MultiAgentCoordinator:
    """
    多 Agent 协调器
    实现多个 Agent 之间的协作和通信
    """

    def __init__(self, llm_client_url: str = "http://model-adapter:8005"):
        self.llm_client_url = llm_client_url
        self.agents: Dict[str, Agent] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.agent_states: Dict[str, str] = {}  # agent_name -> state

    def register_agent(self, agent: Agent):
        """
        注册 Agent

        Args:
            agent: Agent 对象
        """
        self.agents[agent.name] = agent
        self.agent_states[agent.name] = "idle"
        logger.info(f"Registered agent: {agent.name} (role: {agent.role.value})")

    async def execute_collaborative_task(
        self,
        task: str,
        required_roles: List[AgentRole] = None
    ) -> Dict:
        """
        协作执行任务

        Args:
            task: 任务描述
            required_roles: 需要的 Agent 角色

        Returns:
            Dict: 执行结果
        """
        logger.info(f"Starting collaborative task: {task}")

        # 1. 任务分解
        subtasks = await self._decompose_task(task)
        logger.info(f"Decomposed into {len(subtasks)} subtasks")

        # 2. 分配任务给合适的 Agent
        assignments = await self._assign_tasks(subtasks, required_roles)
        logger.info(f"Created {len(assignments)} assignments")

        # 3. 并行执行（或串行，根据依赖关系）
        results = await self._execute_assignments(assignments)

        # 4. 合并结果
        final_result = await self._merge_results(task, results)

        logger.info("Collaborative task completed")
        return final_result

    async def _decompose_task(self, task: str) -> List[Dict]:
        """
        任务分解
        使用 Planner Agent 分解任务

        Returns:
            List[Dict]: 子任务列表
        """
        # 查找 Planner Agent
        planner = self._find_agent_by_role(AgentRole.PLANNER)
        if not planner:
            # 如果没有 Planner，使用简单分解
            return [{
                "id": 1,
                "description": task,
                "required_role": AgentRole.EXECUTOR,
                "dependencies": []
            }]

        # 调用 Planner 进行任务分解
        prompt = f"""作为任务规划专家，请将以下任务分解为可执行的子任务：

任务: {task}

可用角色:
- RESEARCHER: 负责信息搜索和研究
- WRITER: 负责内容创作和编写
- CRITIC: 负责审查和评估
- EXECUTOR: 负责执行具体操作

请返回 JSON 格式的子任务列表：
[
    {{
        "id": 1,
        "description": "子任务描述",
        "required_role": "RESEARCHER",
        "dependencies": []
    }},
    ...
]
"""

        import json

        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": planner.llm_model,
                        "messages": [
                            {"role": "system", "content": "你是一个任务规划专家。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析 JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                subtasks = json.loads(content)
                return subtasks

        except Exception as e:
            logger.error(f"Task decomposition failed: {e}")
            # 降级：返回单个任务
            return [{
                "id": 1,
                "description": task,
                "required_role": AgentRole.EXECUTOR.value,
                "dependencies": []
            }]

    async def _assign_tasks(
        self,
        subtasks: List[Dict],
        required_roles: List[AgentRole] = None
    ) -> List[Tuple[Agent, Dict]]:
        """
        分配任务给 Agent

        Args:
            subtasks: 子任务列表
            required_roles: 需要的角色列表

        Returns:
            List[Tuple[Agent, Dict]]: (Agent, 子任务) 对列表
        """
        assignments = []

        for subtask in subtasks:
            # 确定需要的角色
            required_role_str = subtask.get("required_role", "EXECUTOR")
            try:
                required_role = AgentRole[required_role_str.upper()]
            except KeyError:
                required_role = AgentRole.EXECUTOR

            # 选择合适的 Agent
            agent = self._find_agent_by_role(required_role)

            if agent:
                assignments.append((agent, subtask))
                logger.info(f"Assigned subtask {subtask['id']} to {agent.name}")
            else:
                logger.warning(f"No agent found for role: {required_role}")

        return assignments

    async def _execute_assignments(
        self,
        assignments: List[Tuple[Agent, Dict]]
    ) -> List[Dict]:
        """
        执行分配的任务

        Args:
            assignments: (Agent, 子任务) 对列表

        Returns:
            List[Dict]: 执行结果列表
        """
        # 按依赖关系排序并执行
        results = []
        completed_ids = set()

        while len(results) < len(assignments):
            # 找到可以执行的任务（依赖已完成）
            executable = []
            for agent, subtask in assignments:
                task_id = subtask["id"]
                if task_id in completed_ids:
                    continue

                dependencies = subtask.get("dependencies", [])
                if all(dep_id in completed_ids for dep_id in dependencies):
                    executable.append((agent, subtask))

            if not executable:
                # 避免死锁
                logger.warning("No executable tasks found, breaking...")
                break

            # 并行执行可执行的任务
            tasks = [
                self._execute_subtask(agent, subtask)
                for agent, subtask in executable
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(batch_results):
                agent, subtask = executable[i]
                task_id = subtask["id"]

                if isinstance(result, Exception):
                    logger.error(f"Task {task_id} failed: {result}")
                    results.append({
                        "task_id": task_id,
                        "agent": agent.name,
                        "result": f"Error: {str(result)}",
                        "success": False
                    })
                else:
                    results.append(result)

                completed_ids.add(task_id)

        return results

    async def _execute_subtask(self, agent: Agent, subtask: Dict) -> Dict:
        """
        执行单个子任务

        Args:
            agent: 执行的 Agent
            subtask: 子任务

        Returns:
            Dict: 执行结果
        """
        logger.info(f"Agent {agent.name} executing subtask {subtask['id']}")

        # 更新 Agent 状态
        self.agent_states[agent.name] = "busy"

        try:
            # 构建 prompt
            role_description = {
                AgentRole.RESEARCHER: "你是一个研究专家，擅长搜索和分析信息。",
                AgentRole.WRITER: "你是一个专业写作者，擅长创作高质量内容。",
                AgentRole.CRITIC: "你是一个严格的评审专家，擅长发现问题和提出改进建议。",
                AgentRole.EXECUTOR: "你是一个执行专家，擅长完成具体任务。",
                AgentRole.PLANNER: "你是一个规划专家，擅长任务分解和计划制定。"
            }

            system_message = role_description.get(agent.role, "你是一个智能助手。")
            user_message = f"请完成以下任务：\n\n{subtask['description']}"

            # 调用 LLM
            import httpx

            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": agent.llm_model,
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": agent.temperature,
                        "max_tokens": agent.max_tokens
                    }
                )
                response.raise_for_status()

                result = response.json()
                answer = result["choices"][0]["message"]["content"]

            return {
                "task_id": subtask["id"],
                "agent": agent.name,
                "role": agent.role.value,
                "result": answer,
                "success": True
            }

        except Exception as e:
            logger.error(f"Subtask execution failed: {e}")
            return {
                "task_id": subtask["id"],
                "agent": agent.name,
                "result": f"Error: {str(e)}",
                "success": False
            }

        finally:
            self.agent_states[agent.name] = "idle"

    async def _merge_results(self, original_task: str, results: List[Dict]) -> Dict:
        """
        合并所有 Agent 的结果

        Args:
            original_task: 原始任务
            results: Agent 执行结果列表

        Returns:
            Dict: 最终结果
        """
        # 构建结果摘要
        results_text = "\n\n".join([
            f"[{r['agent']} - {r['role']}]\n{r['result']}"
            for r in results
            if r.get("success")
        ])

        prompt = f"""基于多个 Agent 的协作结果，请生成对原始任务的完整回答。

原始任务: {original_task}

各 Agent 的执行结果:
{results_text}

请整合所有信息，生成清晰、完整、连贯的最终答案。
"""

        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {"role": "system", "content": "你是一个善于整合和总结信息的助手。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.5
                    }
                )
                response.raise_for_status()

                result = response.json()
                final_answer = result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Result merging failed: {e}")
            # 降级：简单拼接
            final_answer = results_text

        return {
            "answer": final_answer,
            "agent_results": results,
            "agents_used": [r["agent"] for r in results],
            "success": all(r.get("success") for r in results)
        }

    def _find_agent_by_role(self, role: AgentRole) -> Optional[Agent]:
        """查找指定角色的 Agent"""
        for agent in self.agents.values():
            if agent.role == role:
                return agent
        return None

    def get_agent_status(self) -> Dict:
        """获取所有 Agent 的状态"""
        return {
            "agents": [
                {
                    "name": agent.name,
                    "role": agent.role.value,
                    "state": self.agent_states.get(agent.name, "unknown"),
                    "capabilities": agent.capabilities
                }
                for agent in self.agents.values()
            ]
        }
