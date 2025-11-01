"""
Plan-Execute Executor
基于计划-执行模式的 Agent 执行器
增强版：OpenTelemetry 追踪、超时控制、指标上报
"""

import asyncio
import json
import logging
from collections.abc import Generator
from datetime import datetime
from typing import Any

import httpx

from app.models.agent_models import AgentResult, Plan, Step, StepResult
from app.services.tool_service import ToolService

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not available, tracing disabled")

# 初始化 tracer
if OTEL_AVAILABLE:
    tracer = trace.get_tracer(__name__)
else:
    # 创建一个空的 tracer stub
    class NoOpSpan:
        def set_attribute(self, *args: Any, **kwargs: Any) -> None:
            pass

        def set_status(self, *args: Any, **kwargs: Any) -> None:
            pass

        def record_exception(self, *args: Any, **kwargs: Any) -> None:
            pass

    class NoOpTracer:
        def start_as_current_span(self, _name: str, **_kwargs: Any) -> Any:
            from contextlib import contextmanager

            @contextmanager
            def noop() -> Generator[NoOpSpan, Any, Any]:
                yield NoOpSpan()

            return noop()

    tracer = NoOpTracer()


class PlanExecuteExecutor:
    """
    Plan-Execute 模式执行器
    1. 使用 LLM 将复杂任务分解为子任务
    2. 为每个子任务生成执行计划
    3. 按顺序或并行执行子任务
    4. 汇总结果生成最终答案
    """

    def __init__(self, llm_client_url: str = "http://model-adapter:8005"):
        self.llm_client_url = llm_client_url
        self.tool_service = ToolService()
        self.max_steps = 10
        self.timeout = 300  # 5分钟

    async def execute(self, task: str, context: dict = None) -> AgentResult:
        """
        执行计划-执行流程 - 增强版（带追踪和超时控制）

        Args:
            task: 用户任务描述
            context: 上下文信息

        Returns:
            AgentResult: 执行结果
        """
        with tracer.start_as_current_span(
            "plan_execute.execute",
            attributes={
                "task": task[:100] if len(task) > 100 else task,  # 截断避免太长
                "has_context": context is not None,
            },
        ) as span:
            start_time = datetime.utcnow()
            logger.info(f"Plan-Execute started: {task}")

            try:
                # 添加整体超时控制（Python 3.11+）
                try:
                    async with asyncio.timeout(self.timeout):
                        return await self._execute_with_tracing(task, context, span, start_time)
                except AttributeError:
                    # Python 3.10 及以下，使用 wait_for
                    return await asyncio.wait_for(
                        self._execute_with_tracing(task, context, span, start_time),
                        timeout=self.timeout,
                    )

            except TimeoutError:
                duration = (datetime.utcnow() - start_time).total_seconds()
                if OTEL_AVAILABLE:
                    span.set_status(Status(StatusCode.ERROR, "Execution timeout"))
                    span.set_attribute("timeout_seconds", self.timeout)
                logger.error(f"Plan-Execute timeout after {duration}s (limit: {self.timeout}s)")

                return AgentResult(
                    answer="执行超时，请稍后重试或简化任务",
                    plan=None,
                    step_results=[],
                    success=False,
                    duration=duration,
                    error="timeout",
                )

            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                if OTEL_AVAILABLE:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error(f"Plan-Execute failed: {e}", exc_info=True)

                return AgentResult(
                    answer=f"执行失败: {str(e)}",
                    plan=None,
                    step_results=[],
                    success=False,
                    duration=duration,
                    error=str(e),
                )

    async def _execute_with_tracing(
        self,
        task: str,
        context: dict,
        span: Any,
        start_time: datetime,
    ) -> AgentResult:
        """内部执行逻辑（带追踪）"""
        # Step 1: 生成执行计划
        with tracer.start_as_current_span("plan_execute.generate_plan"):
            plan = await self._generate_plan(task, context)
            if OTEL_AVAILABLE:
                span.set_attribute("plan_steps_count", len(plan.steps))
            logger.info(f"Generated plan with {len(plan.steps)} steps")

        # Step 2: 执行各个步骤
        step_results = []
        for step in plan.steps:
            with tracer.start_as_current_span(
                f"plan_execute.step_{step.id}",
                attributes={
                    "step_id": step.id,
                    "step_description": step.description[:100]
                    if len(step.description) > 100
                    else step.description,
                    "step_tool": step.tool or "llm",
                },
            ) as step_span:
                # 检查依赖是否完成
                if not self._check_dependencies(step, step_results):
                    logger.warning(f"Step {step.id} dependencies not met, waiting...")
                    await asyncio.sleep(1)

                # 执行步骤
                result = await self._execute_step(step, step_results, context)
                step_results.append(result)

                if OTEL_AVAILABLE:
                    step_span.set_attribute("step_status", result.status)
                    step_span.set_attribute("step_duration", result.duration)

                logger.info(
                    f"Completed step {step.id}: {step.description} (status: {result.status})"
                )

                # 检查是否超过最大步骤数
                if len(step_results) >= self.max_steps:
                    logger.warning(f"Reached max steps limit: {self.max_steps}")
                    break

        # Step 3: 汇总结果
        with tracer.start_as_current_span("plan_execute.summarize"):
            final_answer = await self._summarize_results(task, plan, step_results)

        duration = (datetime.utcnow() - start_time).total_seconds()

        # 记录最终指标
        if OTEL_AVAILABLE:
            span.set_attribute("duration_seconds", duration)
            span.set_attribute("total_steps", len(step_results))
            span.set_attribute("success", True)
            span.set_status(Status(StatusCode.OK))

        return AgentResult(
            answer=final_answer,
            plan=plan,
            step_results=step_results,
            success=True,
            duration=duration,
            metadata={"total_steps": len(step_results), "plan_steps": len(plan.steps)},
        )

    async def _generate_plan(self, task: str, context: dict = None) -> Plan:
        """
        使用 LLM 生成执行计划
        """
        # 构建 prompt
        tools_description = self._get_tools_description()
        context_str = json.dumps(context, ensure_ascii=False) if context else ""

        prompt = f"""你是一个任务规划专家。请将以下任务分解为多个可执行的子任务。

任务: {task}

{f"上下文信息: {context_str}" if context else ""}

可用工具:
{tools_description}

请按照以下 JSON 格式返回计划:
{{
    "steps": [
        {{
            "id": 1,
            "description": "子任务描述",
            "tool": "工具名称",
            "params": {{"param1": "value1"}},
            "dependencies": []
        }},
        {{
            "id": 2,
            "description": "子任务描述2",
            "tool": "工具名称",
            "params": {{"param1": "value1"}},
            "dependencies": [1]
        }}
    ],
    "reasoning": "分解任务的思路"
}}

注意:
1. 将复杂任务分解为简单、可执行的子任务
2. 标明子任务之间的依赖关系
3. 为每个子任务选择合适的工具
4. 确保步骤顺序合理
"""

        # 调用 LLM
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一个任务规划专家，擅长将复杂任务分解为可执行的步骤。",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析 JSON
                # 清理可能的 markdown 代码块标记
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                plan_data = json.loads(content)

                # 转换为 Plan 对象
                steps = []
                for step_data in plan_data["steps"]:
                    steps.append(
                        Step(
                            id=step_data["id"],
                            description=step_data["description"],
                            tool=step_data.get("tool"),
                            params=step_data.get("params", {}),
                            dependencies=step_data.get("dependencies", []),
                        )
                    )

                return Plan(steps=steps, reasoning=plan_data.get("reasoning", ""))

        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            # 返回简单的单步计划作为降级
            return Plan(
                steps=[Step(id=1, description=task, tool=None, params={}, dependencies=[])],
                reasoning="Failed to generate detailed plan, using simple fallback",
            )

    async def _execute_step(
        self, step: Step, previous_results: list[StepResult], context: dict = None
    ) -> StepResult:
        """
        执行单个步骤（带追踪）
        """
        start_time = datetime.utcnow()

        try:
            # 获取依赖步骤的结果
            dependency_outputs = {}
            for dep_id in step.dependencies:
                for result in previous_results:
                    if result.step_id == dep_id:
                        dependency_outputs[f"step_{dep_id}_output"] = result.output

            # 如果指定了工具，使用工具执行
            if step.tool:
                # 合并参数（包含依赖输出）
                params = {**step.params, **dependency_outputs}

                output = await self.tool_service.execute_tool(
                    tool_name=step.tool,
                    params=params,  # type: ignore
                )
            else:
                # 没有指定工具，使用 LLM 直接处理
                output = await self._llm_process_step(step, dependency_outputs, context)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return StepResult(
                step_id=step.id,
                description=step.description,
                output=output,
                status="completed",
                duration=duration,
            )

        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            return StepResult(
                step_id=step.id,
                description=step.description,
                output=f"执行失败: {str(e)}",
                status="failed",
                duration=duration,
                error=str(e),
            )

    async def _llm_process_step(
        self, step: Step, dependency_outputs: dict, context: dict = None
    ) -> str:
        """
        使用 LLM 处理步骤（当没有合适工具时）
        """
        prompt = f"""请完成以下任务:

任务: {step.description}

{f"依赖步骤的输出: {json.dumps(dependency_outputs, ensure_ascii=False)}" if dependency_outputs else ""}
{f"上下文信息: {json.dumps(context, ensure_ascii=False)}" if context else ""}

请直接给出答案，不要额外解释。
"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 1000,
                    },
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]  # type: ignore

        except Exception as e:
            logger.error(f"LLM process step failed: {e}")
            return f"LLM 处理失败: {str(e)}"

    async def _summarize_results(
        self,
        task: str,
        _plan: Plan,
        step_results: list[StepResult],
    ) -> str:  # type: ignore
        """
        汇总所有步骤结果，生成最终答案
        """
        # 构建汇总 prompt
        results_str = "\n".join(
            [f"步骤 {r.step_id}: {r.description}\n结果: {r.output}\n" for r in step_results]
        )

        prompt = f"""基于以下执行结果，请生成对原始任务的完整回答。

原始任务: {task}

执行步骤和结果:
{results_str}

请整合所有信息，给出清晰、完整的最终答案。
"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.llm_client_url}/api/v1/chat/completions",
                    json={
                        "model": "gpt-4-turbo-preview",
                        "messages": [
                            {"role": "system", "content": "你是一个善于总结和整合信息的助手。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.5,
                        "max_tokens": 1500,
                    },
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]  # type: ignore

        except Exception as e:
            logger.error(f"Failed to summarize results: {e}")
            # 降级：简单拼接结果
            return "\n\n".join(
                [
                    f"**{r.description}**\n{r.output}"
                    for r in step_results
                    if r.status == "completed"
                ]
            )

    def _check_dependencies(
        self,
        step: Step,
        completed_results: list[StepResult],
    ) -> bool:
        """
        检查步骤的依赖是否都已完成
        """
        if not step.dependencies:
            return True

        completed_ids = {r.step_id for r in completed_results if r.status == "completed"}
        return all(dep_id in completed_ids for dep_id in step.dependencies)

    def _get_tools_description(self) -> str:  # type: ignore
        """
        获取可用工具的描述
        """
        tools = self.tool_service.list_tools()
        descriptions = []

        for tool in tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")

        return "\n".join(descriptions)
