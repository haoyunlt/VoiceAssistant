"""
Plan-Execute Executor - 规划-执行执行器

将复杂任务分解为多个步骤，逐步执行并综合结果
"""

import asyncio
from typing import Dict, List, Optional

from app.core.logging_config import get_logger
from app.executors.planner import Plan, Planner, Step
from app.tools.dynamic_registry import get_tool_registry
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class StepResult(BaseModel):
    """步骤执行结果"""

    step_id: int = Field(..., description="步骤 ID")
    success: bool = Field(..., description="是否成功")
    result: str = Field("", description="执行结果")
    error: Optional[str] = Field(None, description="错误信息")
    execution_time_ms: float = Field(0.0, description="执行时长（毫秒）")


class ExecutionTrace(BaseModel):
    """执行追踪"""

    task: str = Field(..., description="任务描述")
    plan: Plan = Field(..., description="执行计划")
    step_results: List[StepResult] = Field(
        default_factory=list, description="步骤结果列表"
    )
    final_answer: str = Field("", description="最终答案")
    total_time_ms: float = Field(0.0, description="总执行时长（毫秒）")
    success: bool = Field(True, description="整体是否成功")


class PlanExecuteExecutor:
    """规划-执行执行器"""

    def __init__(self, llm_client=None, max_retries: int = 2):
        """
        初始化执行器

        Args:
            llm_client: LLM 客户端
            max_retries: 步骤失败时的最大重试次数
        """
        self.planner = Planner(llm_client=llm_client)
        self.tool_registry = get_tool_registry()
        self.llm_client = llm_client
        self.max_retries = max_retries

        logger.info("PlanExecuteExecutor initialized")

    async def execute(self, task: str, context: Optional[dict] = None) -> ExecutionTrace:
        """
        执行任务

        Args:
            task: 任务描述
            context: 上下文信息

        Returns:
            ExecutionTrace 对象
        """
        import time

        start_time = time.time()

        try:
            # Phase 1: 规划
            logger.info(f"=== Phase 1: Planning ===")
            available_tools = self._get_available_tools()
            plan = await self.planner.create_plan(task, available_tools, context)
            logger.info(f"Plan created: {len(plan.steps)} steps")
            logger.info(f"Reasoning: {plan.reasoning}")

            # Phase 2: 执行
            logger.info(f"=== Phase 2: Execution ===")
            step_results = await self._execute_plan(plan)

            # Phase 3: 综合
            logger.info(f"=== Phase 3: Synthesis ===")
            final_answer = await self._synthesize_answer(task, plan, step_results)

            total_time = (time.time() - start_time) * 1000

            # 检查是否有失败的步骤
            success = all(result.success for result in step_results)

            return ExecutionTrace(
                task=task,
                plan=plan,
                step_results=step_results,
                final_answer=final_answer,
                total_time_ms=total_time,
                success=success,
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            total_time = (time.time() - start_time) * 1000

            return ExecutionTrace(
                task=task,
                plan=Plan(task=task, steps=[], reasoning="执行失败"),
                step_results=[],
                final_answer=f"执行失败: {str(e)}",
                total_time_ms=total_time,
                success=False,
            )

    async def _execute_plan(self, plan: Plan) -> List[StepResult]:
        """
        执行计划

        Args:
            plan: 执行计划

        Returns:
            步骤结果列表
        """
        step_results: List[StepResult] = []
        results_map: Dict[int, StepResult] = {}  # step_id -> result

        for step in plan.steps:
            # 检查依赖
            if not self._check_dependencies(step, results_map):
                logger.warning(
                    f"Step {step.step_id} dependencies not met, skipping"
                )
                step_results.append(
                    StepResult(
                        step_id=step.step_id,
                        success=False,
                        error="依赖步骤未成功",
                    )
                )
                continue

            # 执行步骤（带重试）
            result = await self._execute_step_with_retry(step, results_map)
            step_results.append(result)
            results_map[step.step_id] = result

            logger.info(
                f"Step {step.step_id} completed: success={result.success}, time={result.execution_time_ms:.2f}ms"
            )

        return step_results

    def _check_dependencies(
        self, step: Step, results_map: Dict[int, StepResult]
    ) -> bool:
        """
        检查步骤依赖是否满足

        Args:
            step: 步骤
            results_map: 已执行步骤的结果映射

        Returns:
            是否满足依赖
        """
        for dep_id in step.depends_on:
            if dep_id not in results_map:
                return False
            if not results_map[dep_id].success:
                return False
        return True

    async def _execute_step_with_retry(
        self, step: Step, results_map: Dict[int, StepResult]
    ) -> StepResult:
        """
        执行步骤（带重试）

        Args:
            step: 步骤
            results_map: 已执行步骤的结果映射

        Returns:
            步骤结果
        """
        for attempt in range(self.max_retries + 1):
            result = await self._execute_step(step, results_map)

            if result.success:
                return result

            if attempt < self.max_retries:
                logger.warning(
                    f"Step {step.step_id} failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying..."
                )
                await asyncio.sleep(0.5)  # 短暂延迟
            else:
                logger.error(
                    f"Step {step.step_id} failed after {self.max_retries + 1} attempts"
                )

        return result

    async def _execute_step(
        self, step: Step, results_map: Dict[int, StepResult]
    ) -> StepResult:
        """
        执行单个步骤

        Args:
            step: 步骤
            results_map: 已执行步骤的结果映射

        Returns:
            步骤结果
        """
        import time

        start_time = time.time()

        try:
            # 如果步骤不需要工具，跳过
            if not step.tool:
                return StepResult(
                    step_id=step.step_id,
                    success=True,
                    result=f"步骤 {step.step_id}: {step.description}（无需执行）",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # 准备工具参数（可能引用之前步骤的结果）
            tool_args = self._prepare_tool_args(step, results_map)

            # 执行工具
            result = await self.tool_registry.execute_tool(step.tool, tool_args)

            # 检查结果
            if result.get("success", True):
                return StepResult(
                    step_id=step.step_id,
                    success=True,
                    result=str(result.get("result", "")),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            else:
                return StepResult(
                    step_id=step.step_id,
                    success=False,
                    error=str(result.get("error", "Unknown error")),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        except Exception as e:
            logger.error(f"Step {step.step_id} execution failed: {e}", exc_info=True)
            return StepResult(
                step_id=step.step_id,
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _prepare_tool_args(
        self, step: Step, results_map: Dict[int, StepResult]
    ) -> dict:
        """
        准备工具参数

        可能需要引用之前步骤的结果

        Args:
            step: 步骤
            results_map: 已执行步骤的结果映射

        Returns:
            工具参数字典
        """
        tool_args = step.tool_args.copy()

        # 处理参数中的引用（如 "${step_1_result}"）
        for key, value in tool_args.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # 提取引用的步骤 ID
                import re

                match = re.match(r"\$\{step_(\d+)_result\}", value)
                if match:
                    ref_step_id = int(match.group(1))
                    if ref_step_id in results_map:
                        tool_args[key] = results_map[ref_step_id].result
                    else:
                        logger.warning(
                            f"Referenced step {ref_step_id} not found in results"
                        )

        return tool_args

    async def _synthesize_answer(
        self, task: str, plan: Plan, step_results: List[StepResult]
    ) -> str:
        """
        综合所有步骤结果，生成最终答案

        Args:
            task: 原始任务
            plan: 执行计划
            step_results: 步骤结果列表

        Returns:
            最终答案
        """
        try:
            # 收集所有成功的步骤结果
            successful_results = [
                f"步骤 {r.step_id}: {r.result}"
                for r in step_results
                if r.success and r.result
            ]

            if not successful_results:
                return "未能获取有效结果"

            # 如果有 LLM，使用 LLM 综合答案
            if self.llm_client:
                synthesis_prompt = f"""
任务: {task}

执行过程:
{chr(10).join(successful_results)}

请基于以上执行过程，生成一个简洁、准确的答案。
"""
                # TODO: 调用 LLM
                # final_answer = await self._call_llm(synthesis_prompt)
                final_answer = (
                    f"基于执行结果，答案是：\n" + "\n".join(successful_results)
                )
            else:
                # 简单拼接
                final_answer = "\n".join(successful_results)

            return final_answer

        except Exception as e:
            logger.error(f"Answer synthesis failed: {e}", exc_info=True)
            return f"综合答案失败: {str(e)}"

    def _get_available_tools(self) -> List[dict]:
        """
        获取可用工具列表

        Returns:
            工具定义列表
        """
        tools = self.tool_registry.list_tools()
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
            }
            for tool in tools
        ]


# 全局执行器实例
_plan_execute_executor: Optional[PlanExecuteExecutor] = None


def get_plan_execute_executor() -> PlanExecuteExecutor:
    """
    获取 Plan-Execute 执行器实例（单例）

    Returns:
        PlanExecuteExecutor 实例
    """
    global _plan_execute_executor

    if _plan_execute_executor is None:
        _plan_execute_executor = PlanExecuteExecutor()

    return _plan_execute_executor
