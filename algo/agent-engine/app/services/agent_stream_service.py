"""Agent流式执行服务"""
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.models.agent import AgentTask
from app.services.llm_service import LLMService
from app.services.tool_service import ToolService


class StepType(str, Enum):
    """步骤类型"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class AgentStepResult:
    """Agent步骤结果"""
    step_type: StepType
    content: str = ""
    is_partial: bool = False
    tool_name: str | None = None
    parameters: dict[str, Any] | None = None
    error: str | None = None
    iteration: int = 0


class AgentContext:
    """Agent执行上下文"""

    def __init__(self, task: AgentTask):
        self.task = task
        self.messages: list[dict[str, str]] = []
        self.steps: list[dict[str, Any]] = []
        self.final_answer = ""

    def add_step(self, thought: str, action: dict | None, observation: str) -> None:
        """添加执行步骤"""
        self.steps.append({
            "thought": thought,
            "action": action,
            "observation": observation
        }  # type: ignore)

        # 更新messages
        self.messages.append({  # type: ignore
            "role": "assistant",
            "content": thought
        }  # type: ignore
        if action:  # type: ignore
            self.messages.append({  # type: ignore
                "role": "user",
                "content": f"Observation: {observation}"
            }  # type: ignore


class AgentStreamService:
    """Agent流式服务"""

    def __init__(self, llm_service: LLMService, tool_service: ToolService):
        self.llm_service = llm_service
        self.tool_service = tool_service

    async def execute_stream(
        self,
        task: AgentTask
    ) -> AsyncIterator[AgentStepResult]:
        """流式执行Agent任务"""

        # 初始化上下文
        context = self._init_context(task)
        iteration = 0

        try:
            while iteration < task.max_iterations:
                iteration += 1

                # 1. Thought阶段 - 流式返回
                thought_chunk = ""
                async for chunk in self.llm_service.chat_stream(
                    messages=context.messages,
                    model=task.model,
                    temperature=task.temperature
                ):
                    thought_chunk += chunk
                    yield AgentStepResult(
                        step_type=StepType.THOUGHT,
                        content=chunk,
                        is_partial=True,
                        iteration=iteration
                    )

                # 2. 解析Action
                action = self._parse_action(thought_chunk)

                if action is None:
                    # 最终答案
                    final_answer = self._extract_final_answer(thought_chunk)
                    context.final_answer = final_answer

                    yield AgentStepResult(
                        step_type=StepType.FINAL_ANSWER,
                        content=final_answer,
                        is_partial=False,
                        iteration=iteration
                    )
                    break

                # 返回Action信息
                yield AgentStepResult(
                    step_type=StepType.ACTION,
                    tool_name=action["tool"],
                    parameters=action["parameters"],
                    is_partial=False,
                    iteration=iteration
                )

                # 3. 执行Tool（带容错）
                try:
                    observation = await self._execute_tool_with_retry(
                        tool_name=action["tool"],
                        parameters=action["parameters"],
                        timeout=task.tool_timeout
                    )
                except ToolExecutionError as e:
                    observation = f"❌ Tool execution error: {str(e)}"
                except Exception as e:
                    observation = f"❌ Unexpected error: {str(e)}"

                yield AgentStepResult(
                    step_type=StepType.OBSERVATION,
                    content=observation,
                    is_partial=False,
                    iteration=iteration
                )

                # 4. 更新上下文
                context.add_step(thought_chunk, action, observation)

            # 完成信号
            yield AgentStepResult(
                step_type=StepType.COMPLETED,
                content=context.final_answer,
                is_partial=False,
                iteration=iteration
            )

        except Exception as e:
            yield AgentStepResult(
                step_type=StepType.ERROR,
                error=str(e),
                is_partial=False,
                iteration=iteration
            )

    def _init_context(self, task: AgentTask) -> AgentContext:
        """初始化上下文"""
        context = AgentContext(task)

        # 构建系统提示词
        system_prompt = self._build_system_prompt(task)
        context.messages.append({
            "role": "system",
            "content": system_prompt
        })

        # 添加用户问题
        context.messages.append({
            "role": "user",
            "content": task.query
        })

        return context

    def _build_system_prompt(self, task: AgentTask) -> str:
        """构建系统提示词"""
        tools_desc = self.tool_service.get_tools_description()

        return f"""You are a helpful AI assistant with access to tools.

Available Tools:
{tools_desc}

You should think step by step and use tools when needed.

Response Format:
Thought: [Your reasoning process]
Action: [tool_name]
Action Input: {{"param1": "value1", "param2": "value2"}}

After receiving observation, continue with:
Thought: [Analysis of observation]
...

When you have the final answer:
Thought: I now have the final answer
Final Answer: [Your complete answer]
"""

    def _parse_action(self, thought: str) -> dict[str, Any] | None:
        """解析Action"""
        # 简化的解析逻辑
        if "Final Answer:" in thought:
            return None

        # 提取Action
        if "Action:" not in thought:
            return None

        try:
            action_line = [line for line in thought.split('\n') if line.startswith('Action:')][0]
            tool_name = action_line.replace('Action:', '').strip()

            # 提取参数
            input_line = [line for line in thought.split('\n') if line.startswith('Action Input:')][0]
            import json
            params_str = input_line.replace('Action Input:', '').strip()
            parameters = json.loads(params_str)

            return {
                "tool": tool_name,
                "parameters": parameters
            }
        except Exception:
            return None

    def _extract_final_answer(self, thought: str) -> str:
        """提取最终答案"""
        if "Final Answer:" in thought:
            parts = thought.split("Final Answer:")
            if len(parts) > 1:
                return parts[1].strip()
        return thought.strip()

    async def _execute_tool_with_retry(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int = 30,
        max_retries: int = 3
    ) -> str:
        """带重试的工具执行"""
        last_error = None

        for attempt in range(max_retries):
            try:
                result = await self.tool_service.execute_tool(
                    tool_name=tool_name,
                    parameters=parameters,
                    timeout=timeout
                )
                return self._format_result(result)
            except ToolExecutionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    # 指数退避
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise

        if last_error:
            raise last_error

    def _format_result(self, result: Any) -> str:
        """格式化结果"""
        if isinstance(result, str):
            return result
        elif isinstance(result, (dict, list)):
            import json
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return str(result)
