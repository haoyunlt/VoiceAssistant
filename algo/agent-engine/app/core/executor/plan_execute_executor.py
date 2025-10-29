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

    def __init__(self, llm_client, tool_registry):
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        logger.info("Plan-Execute executor created")

    async def execute(
        self,
        task: str,
        max_steps: int = 10,
        available_tools: list[dict] = None,
        memory: dict = None,
    ) -> dict:
        """执行任务（非流式）"""
        # 1. 制定计划
        plan = await self._make_plan(task, available_tools)

        # 2. 执行计划
        results = []
        for i, step in enumerate(plan[:max_steps], 1):
            result = await self._execute_step(step, available_tools)
            results.append({
                "step": i,
                "plan": step,
                "result": result,
            })

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
        available_tools: list[dict] = None,
        memory: dict = None,
    ) -> AsyncIterator[str]:
        """执行任务（流式）"""
        # 发送计划
        plan = await self._make_plan(task, available_tools)
        yield json.dumps({"type": "plan", "content": plan})

        # 执行计划
        for i, step in enumerate(plan[:max_steps], 1):
            yield json.dumps({"type": "step_start", "step": i, "plan": step})

            result = await self._execute_step(step, available_tools)

            yield json.dumps({"type": "step_result", "content": result})

        # 汇总
        final_answer = await self._summarize_results(task, [])
        yield json.dumps({"type": "final", "content": final_answer})

    async def _make_plan(self, task: str, tools: list[dict]) -> list[str]:
        """制定计划"""
        prompt = f"""任务: {task}

可用工具: {', '.join([t['name'] for t in tools])}

请制定一个逐步解决该任务的计划，每行一个步骤："""

        response = await self.llm_client.generate(prompt, temperature=0.3, max_tokens=500)
        steps = [s.strip() for s in response.strip().split('\n') if s.strip()]
        return steps

    async def _execute_step(self, step: str, tools: list[dict]) -> str:
        """执行单个步骤"""
        # 简化实现：直接返回步骤描述
        # TODO: 实际应该解析步骤，调用工具
        return f"执行: {step}"

    async def _summarize_results(self, task: str, results: list[dict]) -> str:
        """汇总结果"""
        return f"任务'{task}'已完成"
