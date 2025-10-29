"""Agent执行服务"""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from app.models.agent import (
    AgentResult,
    AgentStatus,
    AgentTask,
)
from app.services.llm_service import LLMService
from app.services.task_manager import task_manager
from app.services.tool_service import ToolService

logger = logging.getLogger(__name__)


class AgentService:
    """Agent执行服务"""

    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.tool_service = ToolService()
        # self.task_results: Dict[str, AgentResult] = {}  # 已迁移到Redis

    def generate_task_id(self) -> str:
        """生成任务ID"""
        return f"task_{uuid.uuid4().hex[:16]}"

    async def execute(self, task: AgentTask) -> AgentResult:
        """
        执行Agent任务（ReAct模式）

        ReAct: Reasoning + Acting
        循环执行：Thought → Action → Observation → 直到完成
        """
        task_id = task.task_id or self.generate_task_id()
        start_time = time.time()
        steps: list[dict[str, Any]] = []

        try:
            logger.info(f"[{task_id}] Starting agent execution: {task.task}")

            # 初始化系统提示
            system_prompt = self._build_system_prompt(task)
            conversation_history = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.task},
            ]

            # ReAct循环
            for iteration in range(task.max_iterations):
                logger.info(f"[{task_id}] Iteration {iteration + 1}/{task.max_iterations}")

                # 1. Thought - 让LLM思考下一步
                thought_response = await self.llm_service.chat(
                    messages=conversation_history,
                    model=task.model,
                    temperature=task.temperature,
                )

                thought_content = thought_response.get("content", "")
                logger.info(f"[{task_id}] Thought: {thought_content[:200]}...")

                # 记录思考步骤
                thought_step = {
                    "step_number": len(steps) + 1,
                    "step_type": "thought",
                    "content": thought_content,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                steps.append(thought_step)

                # 2. 判断是否完成
                if self._is_final_answer(thought_content):
                    # 提取最终答案
                    final_answer = self._extract_answer(thought_content)

                    answer_step = {
                        "step_number": len(steps) + 1,
                        "step_type": "answer",
                        "content": final_answer,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    steps.append(answer_step)

                    execution_time = time.time() - start_time
                    result = AgentResult(
                        task_id=task_id,
                        result=final_answer,
                        steps=steps,
                        status=AgentStatus.COMPLETED,
                        iterations=iteration + 1,
                        execution_time=execution_time,
                        completed_at=datetime.utcnow(),
                    )

                    await task_manager.save_task(result)
                    logger.info(f"[{task_id}] Completed in {execution_time:.2f}s")
                    return result

                # 3. Action - 解析工具调用
                action_info = self._parse_action(thought_content)

                if action_info:
                    tool_name = action_info.get("tool")
                    tool_input = action_info.get("input", {})

                    logger.info(f"[{task_id}] Action: {tool_name} with {tool_input}")

                    # 记录行动步骤
                    action_step = {
                        "step_number": len(steps) + 1,
                        "step_type": "action",
                        "content": f"Using tool: {tool_name}",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    steps.append(action_step)

                    # 4. Observation - 执行工具并观察结果
                    try:
                        tool_output = await self.tool_service.execute_tool(
                            str(tool_name), tool_input
                        )

                        logger.info(f"[{task_id}] Observation: {str(tool_output)[:200]}...")

                        observation_step = {
                            "step_number": len(steps) + 1,
                            "step_type": "observation",
                            "content": str(tool_output),
                            "tool_output": tool_output,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        steps.append(observation_step)

                        # 将观察结果加入对话历史
                        conversation_history.append(
                            {
                                "role": "assistant",
                                "content": thought_content,
                            }
                        )
                        conversation_history.append(
                            {
                                "role": "user",
                                "content": f"Observation: {tool_output}",
                            }
                        )

                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        logger.error(f"[{task_id}] {error_msg}")

                        observation_step = {
                            "step_number": len(steps) + 1,
                            "step_type": "observation",
                            "content": error_msg,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        steps.append(observation_step)

                        conversation_history.append(
                            {
                                "role": "user",
                                "content": f"Error: {error_msg}",
                            }
                        )
                else:
                    # 没有明确的工具调用，继续下一轮思考
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": thought_content,
                        }
                    )

            # 达到最大迭代次数
            execution_time = time.time() - start_time
            result = AgentResult(
                task_id=task_id,
                result="Maximum iterations reached without finding a solution.",
                steps=steps,
                status=AgentStatus.TIMEOUT,
                iterations=task.max_iterations,
                execution_time=execution_time,
                completed_at=datetime.utcnow(),
            )

            await task_manager.save_task(result)
            logger.warning(f"[{task_id}] Timeout after {task.max_iterations} iterations")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[{task_id}] Failed: {error_msg}", exc_info=True)

            result = AgentResult(
                task_id=task_id,
                result="",
                steps=steps,
                status=AgentStatus.FAILED,
                iterations=len(steps),
                execution_time=execution_time,
                error=error_msg,
                completed_at=datetime.utcnow(),
            )

            await task_manager.save_task(result)
            return result

    async def execute_async(self, task: AgentTask) -> None:
        """异步执行任务（后台任务）"""
        await self.execute(task)

    async def get_task_result(self, task_id: str) -> AgentResult | None:
        """获取任务结果"""
        return await task_manager.get_task(task_id)

    def _build_system_prompt(self, task: AgentTask) -> str:
        """构建系统提示"""
        tools_description = self._format_tools_description(task.tools)

        prompt = f"""You are a helpful AI agent that can use tools to accomplish tasks.

Available tools:
{tools_description}

To use a tool, respond with:
Action: <tool_name>
Input: <tool_input_as_json>

When you have the final answer, respond with:
Final Answer: <your_answer>

Think step by step and explain your reasoning before taking actions.
"""
        return prompt

    def _format_tools_description(self, tool_names: list) -> str:
        """格式化工具描述"""
        if not tool_names:
            return "No tools available."

        descriptions = []
        for tool_name in tool_names:
            tool_info = self.tool_service.get_tool_info(tool_name)
            if tool_info:
                descriptions.append(f"- {tool_name}: {tool_info.get('description', '')}")

        return "\n".join(descriptions)

    def _is_final_answer(self, content: str) -> bool:
        """判断是否是最终答案"""
        return "final answer:" in content.lower()

    def _extract_answer(self, content: str) -> str:
        """提取最终答案"""
        # 简单实现：查找"Final Answer:"后的内容
        lower_content = content.lower()
        if "final answer:" in lower_content:
            idx = lower_content.index("final answer:")
            answer = content[idx + len("final answer:") :].strip()
            return answer
        return content

    def _parse_action(self, content: str) -> dict[str, Any] | None:
        """
        解析工具调用

        期望格式:
        Action: <tool_name>
        Input: <json_input>
        """
        import json
        import re

        # 查找 Action: 和 Input:
        action_pattern = r"Action:\s*(\w+)"
        input_pattern = r"Input:\s*(\{.*?\})"

        action_match = re.search(action_pattern, content, re.IGNORECASE)
        input_match = re.search(input_pattern, content, re.IGNORECASE | re.DOTALL)

        if action_match:
            tool_name = action_match.group(1)
            tool_input = {}

            if input_match:
                try:
                    tool_input = json.loads(input_match.group(1))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse tool input: {input_match.group(1)}")

            return {
                "tool": tool_name,
                "input": tool_input,
            }

        return None

    async def execute_stream(self, task: AgentTask) -> AsyncIterator[dict[str, Any]]:
        task_id = task.task_id or self.generate_task_id()
        start_time = time.time()
        steps: list[dict[str, Any]] = []

        try:
            logger.info(f"[{task_id}] Starting streaming agent execution: {task.task}")

            # 发送开始事件
            yield {
                "event_type": "start",
                "task_id": task_id,
                "task": task.task,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # 初始化系统提示
            system_prompt = self._build_system_prompt(task)
            conversation_history = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.task},
            ]

            # ReAct循环
            for iteration in range(task.max_iterations):
                logger.info(f"[{task_id}] Iteration {iteration + 1}/{task.max_iterations}")

                # 1. Thought - 让LLM思考下一步
                thought_response = await self.llm_service.chat(
                    messages=conversation_history,
                    model=task.model,
                    temperature=task.temperature,
                )

                thought_content = thought_response.get("content", "")
                logger.info(f"[{task_id}] Thought: {thought_content[:200]}...")

                # 流式发送思考步骤
                thought_step = {
                    "step_number": len(steps) + 1,
                    "step_type": "thought",
                    "content": thought_content,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                steps.append(thought_step)

                yield {
                    "event_type": "thought",
                    "step_number": thought_step["step_number"],
                    "content": thought_content,
                    "iteration": iteration + 1,
                    "timestamp": thought_step["timestamp"],
                }

                # 2. 判断是否完成
                if self._is_final_answer(thought_content):
                    # 提取最终答案
                    final_answer = self._extract_answer(thought_content)

                    answer_step = {
                        "step_number": len(steps) + 1,
                        "step_type": "answer",
                        "content": final_answer,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    steps.append(answer_step)

                    # 流式发送最终答案
                    yield {
                        "event_type": "answer",
                        "step_number": answer_step["step_number"],
                        "content": final_answer,
                        "timestamp": answer_step["timestamp"],
                    }

                    execution_time = time.time() - start_time
                    result = AgentResult(
                        task_id=task_id,
                        result=final_answer,
                        steps=steps,
                        status=AgentStatus.COMPLETED,
                        iterations=iteration + 1,
                        execution_time=execution_time,
                        completed_at=datetime.utcnow(),
                    )

                    await task_manager.save_task(result)

                    # 发送完成事件
                    yield {
                        "event_type": "complete",
                        "task_id": task_id,
                        "result": final_answer,
                        "iterations": iteration + 1,
                        "execution_time": execution_time,
                        "status": "completed",
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                    logger.info(f"[{task_id}] Completed in {execution_time:.2f}s")
                    return

                # 3. Action - 解析工具调用
                action_info = self._parse_action(thought_content)

                if action_info:
                    tool_name = action_info.get("tool")
                    tool_input = action_info.get("input", {})

                    logger.info(f"[{task_id}] Action: {tool_name} with {tool_input}")

                    # 流式发送行动步骤
                    action_step = {
                        "step_number": len(steps) + 1,
                        "step_type": "action",
                        "content": f"Using tool: {tool_name}",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    steps.append(action_step)

                    yield {
                        "event_type": "action",
                        "step_number": action_step["step_number"],
                        "content": action_step["content"],
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "timestamp": action_step["timestamp"],
                    }

                    # 4. Observation - 执行工具并观察结果
                    try:
                        tool_output = await self.tool_service.execute_tool(
                            str(tool_name), tool_input
                        )

                        logger.info(f"[{task_id}] Observation: {str(tool_output)[:200]}...")

                        observation_step = {
                            "step_number": len(steps) + 1,
                            "step_type": "observation",
                            "content": str(tool_output),
                            "tool_output": tool_output,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        steps.append(observation_step)

                        # 流式发送观察结果
                        yield {
                            "event_type": "observation",
                            "step_number": observation_step["step_number"],
                            "content": str(tool_output),
                            "tool_name": tool_name,
                            "timestamp": observation_step["timestamp"],
                        }

                        # 将观察结果加入对话历史
                        conversation_history.append(
                            {
                                "role": "assistant",
                                "content": thought_content,
                            }
                        )
                        conversation_history.append(
                            {
                                "role": "user",
                                "content": f"Observation: {tool_output}",
                            }
                        )

                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        logger.error(f"[{task_id}] {error_msg}")

                        observation_step = {
                            "step_number": len(steps) + 1,
                            "step_type": "observation",
                            "content": error_msg,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        steps.append(observation_step)

                        # 流式发送错误观察
                        yield {
                            "event_type": "observation",
                            "step_number": observation_step["step_number"],
                            "content": error_msg,
                            "error": True,
                            "timestamp": observation_step["timestamp"],
                        }

                        conversation_history.append(
                            {
                                "role": "user",
                                "content": f"Error: {error_msg}",
                            }
                        )
                else:
                    # 没有明确的工具调用，继续下一轮思考
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": thought_content,
                        }
                    )

            # 达到最大迭代次数
            execution_time = time.time() - start_time
            result = AgentResult(
                task_id=task_id,
                result="Maximum iterations reached without finding a solution.",
                steps=steps,
                status=AgentStatus.TIMEOUT,
                iterations=task.max_iterations,
                execution_time=execution_time,
                completed_at=datetime.utcnow(),
            )

            await task_manager.save_task(result)

            # 发送超时事件
            yield {
                "event_type": "complete",
                "task_id": task_id,
                "result": "Maximum iterations reached",
                "iterations": task.max_iterations,
                "execution_time": execution_time,
                "status": "timeout",
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.warning(f"[{task_id}] Timeout after {task.max_iterations} iterations")

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"[{task_id}] Failed: {error_msg}", exc_info=True)

            result = AgentResult(
                task_id=task_id,
                result="",
                steps=steps,
                status=AgentStatus.FAILED,
                iterations=len(steps),
                execution_time=execution_time,
                error=error_msg,
                completed_at=datetime.utcnow(),
            )

            await task_manager.save_task(result)

            # 发送错误事件
            yield {
                "event_type": "error",
                "task_id": task_id,
                "error": error_msg,
                "execution_time": execution_time,
                "timestamp": datetime.utcnow().isoformat(),
            }
