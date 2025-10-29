"""
ReAct Executor - ReAct (Reasoning + Acting) 模式执行器

核心流程：
1. Thought: 思考当前状况
2. Action: 决定调用哪个工具
3. Observation: 观察工具执行结果
4. 重复直到任务完成或达到最大步骤数
"""

import json
import logging
import re
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class ReActExecutor:
    """ReAct 执行器"""

    def __init__(self, llm_client, tool_registry):
        """
        初始化 ReAct 执行器

        Args:
            llm_client: LLM 客户端
            tool_registry: 工具注册表
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        logger.info("ReAct executor created")

    async def execute(
        self,
        task: str,
        max_steps: int = 10,
        available_tools: list[dict] = None,
        memory: dict = None,
    ) -> dict:
        """
        执行任务（非流式）

        Args:
            task: 任务描述
            max_steps: 最大步骤数
            available_tools: 可用工具列表
            memory: 记忆

        Returns:
            执行结果
        """
        steps = []
        current_step = 0

        # 构建初始 Prompt
        prompt = self._build_initial_prompt(task, available_tools, memory)

        while current_step < max_steps:
            current_step += 1
            logger.info(f"Step {current_step}/{max_steps}")

            # 生成 ReAct 步骤
            react_output = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000,
            )

            # 解析输出
            thought, action, action_input, final_answer = self._parse_react_output(react_output)

            step_info = {
                "step": current_step,
                "thought": thought,
            }

            # 检查是否完成
            if final_answer:
                step_info["final_answer"] = final_answer
                steps.append(step_info)
                logger.info(f"Task completed at step {current_step}")
                break

            # 执行工具调用
            if action:
                step_info["action"] = action
                step_info["action_input"] = action_input

                observation = await self._execute_tool(action, action_input, available_tools)
                step_info["observation"] = observation

                steps.append(step_info)

                # 更新 Prompt（添加观察结果）
                prompt += f"\n{react_output}\n观察: {observation}\n\n继续思考："
            else:
                # 无法解析出有效动作
                step_info["error"] = "Failed to parse action"
                steps.append(step_info)
                break

        return {
            "status": "success" if final_answer else "max_steps_reached",
            "steps": steps,
            "step_count": len(steps),
            "tool_call_count": sum(1 for s in steps if "action" in s),
            "final_answer": final_answer if final_answer else "任务未完成",
        }

    async def execute_stream(
        self,
        task: str,
        max_steps: int = 10,
        available_tools: list[dict] = None,
        memory: dict = None,
    ) -> AsyncIterator[str]:
        """
        执行任务（流式）

        Yields:
            JSON 格式的步骤信息
        """
        current_step = 0
        prompt = self._build_initial_prompt(task, available_tools, memory)

        while current_step < max_steps:
            current_step += 1

            # 发送步骤开始信号
            yield json.dumps({
                "type": "step_start",
                "step": current_step,
            })

            # 生成 ReAct 步骤
            react_output = await self.llm_client.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000,
            )

            # 解析输出
            thought, action, action_input, final_answer = self._parse_react_output(react_output)

            # 发送思考
            if thought:
                yield json.dumps({
                    "type": "thought",
                    "content": thought,
                })

            # 检查是否完成
            if final_answer:
                yield json.dumps({
                    "type": "final",
                    "content": final_answer,
                })
                break

            # 执行工具
            if action:
                yield json.dumps({
                    "type": "action",
                    "action": action,
                    "input": action_input,
                })

                observation = await self._execute_tool(action, action_input, available_tools)

                yield json.dumps({
                    "type": "observation",
                    "content": observation,
                })

                # 更新 Prompt
                prompt += f"\n{react_output}\n观察: {observation}\n\n继续思考："
            else:
                yield json.dumps({
                    "type": "error",
                    "content": "Failed to parse action",
                })
                break

    def _build_initial_prompt(
        self, task: str, available_tools: list[dict], memory: dict
    ) -> str:
        """构建初始 Prompt"""
        # 工具描述
        tools_desc = self._format_tools(available_tools)

        # 记忆描述
        memory_desc = self._format_memory(memory)

        prompt = f"""你是一个智能助手，使用 ReAct 模式解决问题。

可用工具：
{tools_desc}

{memory_desc}

任务：{task}

请按照以下格式逐步思考和行动：

思考: [分析当前状况，决定下一步]
动作: [选择一个工具]
动作输入: [工具的输入参数]
观察: [工具返回的结果]
...（重复思考-动作-观察）
思考: [任务已完成]
最终答案: [给出最终答案]

开始：
"""

        return prompt

    def _format_tools(self, tools: list[dict]) -> str:
        """格式化工具列表"""
        if not tools:
            return "（无可用工具）"

        lines = []
        for tool in tools:
            lines.append(f"- {tool['name']}: {tool['description']}")
            if tool.get("parameters"):
                lines.append(f"  参数: {tool['parameters']}")

        return "\n".join(lines)

    def _format_memory(self, memory: dict) -> str:
        """格式化记忆"""
        if not memory or not memory.get("history"):
            return ""

        return f"历史记录：\n{memory.get('summary', '')}\n"

    def _parse_react_output(self, output: str) -> tuple:
        """
        解析 ReAct 输出

        Returns:
            (thought, action, action_input, final_answer)
        """
        thought = None
        action = None
        action_input = None
        final_answer = None

        # 提取思考
        thought_match = re.search(r"思考[:：]\s*(.*?)(?=\n|动作|最终答案|$)", output, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 提取最终答案
        final_match = re.search(r"最终答案[:：]\s*(.*?)$", output, re.DOTALL)
        if final_match:
            final_answer = final_match.group(1).strip()
            return thought, None, None, final_answer

        # 提取动作
        action_match = re.search(r"动作[:：]\s*(\w+)", output)
        if action_match:
            action = action_match.group(1).strip()

        # 提取动作输入
        input_match = re.search(r"动作输入[:：]\s*(.*?)(?=\n|$)", output, re.DOTALL)
        if input_match:
            action_input = input_match.group(1).strip()

        return thought, action, action_input, final_answer

    async def _execute_tool(
        self, tool_name: str, tool_input: str, available_tools: list[dict]
    ) -> str:
        """执行工具调用"""
        try:
            result = await self.tool_registry.execute_tool(tool_name, tool_input)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"工具执行失败: {str(e)}"
