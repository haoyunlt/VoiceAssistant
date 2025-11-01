"""
Plan-Execute Executor - 计划-执行模式

核心流程：
1. Plan: 制定完整计划
2. Execute: 逐步执行计划
3. Re-plan: 根据结果调整计划（可选）
"""

import json
import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class PlanExecuteExecutor:
    """Plan-Execute 执行器"""

    def __init__(self, llm_client, tool_registry):  # type: ignore
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        logger.info("Plan-Execute executor created")

    async def execute(
        self,
        task: str,
        max_steps: int = 10,
        available_tools: list[dict] | None = None,  # type: ignore
        _memory: dict | None = None,  # type: ignore
    ) -> dict:
        """执行任务（非流式）"""
        # 1. 制定计划
        plan = await self._make_plan(task, available_tools)  # type: ignore [type-arg]

        # 2. 执行计划
        results = []
        for i, step in enumerate(plan[:max_steps], 1):
            result = await self._execute_step(step, available_tools)  # type: ignore [type-arg]
            results.append(
                {
                    "step": i,
                    "plan": step,
                    "result": result,
                }
            )

        # 3. 汇总结果
        final_answer = await self._summarize_results(task, results)

        return {
            "status": "success",
            "plan": plan,
            "steps": results,
            "step_count": len(results),
            "tool_call_count": sum(1 for r in results if r.get("tool_used")),
            "final_answer": final_answer,
        }

    async def execute_stream(
        self,
        task: str,
        max_steps: int = 10,
        available_tools: list[dict] | None = None,  # type: ignore
        _memory: dict | None = None,  # type: ignore [type-arg]
    ) -> AsyncIterator[str]:
        """执行任务（流式）"""
        # 发送计划
        plan = await self._make_plan(task, available_tools)  # type: ignore [type-arg]
        yield json.dumps({"type": "plan", "content": plan})

        # 执行计划
        for i, step in enumerate(plan[:max_steps], 1):
            yield json.dumps({"type": "step_start", "step": i, "plan": step})

            result = await self._execute_step(step, available_tools)  # type: ignore [type-arg]

            yield json.dumps({"type": "step_result", "content": result})

        # 汇总
        final_answer = await self._summarize_results(task, [])
        yield json.dumps({"type": "final", "content": final_answer})

    async def _make_plan(self, task: str, tools: list[dict]) -> list[str]:
        """制定计划"""
        prompt = f"""任务: {task}

可用工具: {", ".join([t["name"] for t in tools])}

请制定一个逐步解决该任务的计划，每行一个步骤："""

        response = await self.llm_client.generate(prompt, temperature=0.3, max_tokens=500)
        steps = [s.strip() for s in response.strip().split("\n") if s.strip()]
        return steps

    async def _execute_step(self, step: str, tools: list[dict]) -> str:
        """执行单个步骤"""
        # 1. 解析步骤，提取工具调用
        tool_call = await self._parse_step_for_tool_call(step, tools)

        if tool_call:
            # 2. 调用工具
            try:
                result = await self.tool_registry.execute_tool(
                    tool_call["tool_name"], **tool_call["arguments"]
                )
                return f"步骤: {step}\n结果: {result}"
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return f"步骤: {step}\n错误: {str(e)}"
        else:
            # 3. 如果无需工具，使用LLM直接回答
            prompt = f"请执行以下步骤: {step}"
            result = await self.llm_client.generate(prompt, temperature=0.3, max_tokens=300)
            return f"步骤: {step}\n结果: {result}"

    async def _parse_step_for_tool_call(self, step: str, tools: list[dict]) -> dict | None:
        """解析步骤，提取工具调用"""
        # 使用LLM解析步骤，判断是否需要调用工具
        tools_desc = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])

        prompt = f"""分析以下步骤，判断是否需要使用工具。

步骤: {step}

可用工具:
{tools_desc}

如果需要使用工具，返回JSON格式:
{{"tool_name": "工具名称", "arguments": {{"参数名": "参数值"}}}}

如果不需要工具，返回: {{"tool_name": null}}"""

        response = await self.llm_client.generate(prompt, temperature=0.0, max_tokens=200)

        try:
            import json

            result = json.loads(response.strip())
            if result.get("tool_name"):
                return result
        except Exception as e:
            logger.warning(f"Failed to parse tool call: {e}")

        return None

    async def _summarize_results(self, task: str, _results: list[dict]) -> str:
        """汇总结果"""
        return f"任务'{task}'已完成"
