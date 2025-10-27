"""
Planner - 任务规划器

使用 LLM 将复杂任务分解为多个步骤
"""

import json
from typing import List, Optional

from app.core.logging_config import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class Step(BaseModel):
    """单个执行步骤"""

    step_id: int = Field(..., description="步骤 ID")
    description: str = Field(..., description="步骤描述")
    tool: Optional[str] = Field(None, description="使用的工具名称")
    tool_args: dict = Field(default_factory=dict, description="工具参数")
    depends_on: List[int] = Field(default_factory=list, description="依赖的步骤 ID")


class Plan(BaseModel):
    """任务执行计划"""

    task: str = Field(..., description="原始任务描述")
    steps: List[Step] = Field(..., description="执行步骤列表")
    reasoning: str = Field("", description="规划推理过程")


class Planner:
    """任务规划器"""

    def __init__(self, llm_client=None):
        """
        初始化规划器

        Args:
            llm_client: LLM 客户端（用于调用 LLM API）
        """
        self.llm_client = llm_client
        logger.info("Planner initialized")

    async def create_plan(
        self,
        task: str,
        available_tools: List[dict],
        context: Optional[dict] = None,
    ) -> Plan:
        """
        创建任务执行计划

        Args:
            task: 任务描述
            available_tools: 可用工具列表
            context: 上下文信息（可选）

        Returns:
            Plan 对象
        """
        try:
            # 构建提示词
            prompt = self._build_planning_prompt(task, available_tools, context)

            # 调用 LLM 生成计划
            if self.llm_client:
                response = await self._call_llm(prompt)
                plan = self._parse_llm_response(response, task)
            else:
                # 如果没有 LLM，使用启发式方法生成简单计划
                plan = self._heuristic_plan(task, available_tools)

            logger.info(f"Plan created with {len(plan.steps)} steps")
            return plan

        except Exception as e:
            logger.error(f"Failed to create plan: {e}", exc_info=True)
            # 返回一个单步骤的降级计划
            return Plan(
                task=task,
                steps=[
                    Step(
                        step_id=1,
                        description=f"完成任务: {task}",
                        tool=None,
                        tool_args={},
                        depends_on=[],
                    )
                ],
                reasoning="规划失败，使用降级策略",
            )

    def _build_planning_prompt(
        self, task: str, available_tools: List[dict], context: Optional[dict]
    ) -> str:
        """
        构建规划提示词

        Args:
            task: 任务描述
            available_tools: 可用工具列表
            context: 上下文信息

        Returns:
            提示词字符串
        """
        tools_desc = "\n".join(
            [
                f"- {tool['name']}: {tool.get('description', 'No description')}"
                for tool in available_tools
            ]
        )

        context_str = ""
        if context:
            context_str = f"\n\n**上下文信息**:\n{json.dumps(context, ensure_ascii=False, indent=2)}"

        prompt = f"""你是一个任务规划助手。请将下面的任务分解为多个可执行的步骤。

**任务**: {task}

**可用工具**:
{tools_desc}
{context_str}

**要求**:
1. 将任务分解为清晰、可执行的步骤
2. 每个步骤应该尽可能原子化（一个步骤做一件事）
3. 如果需要使用工具，指定工具名称和参数
4. 如果步骤之间有依赖关系，使用 depends_on 指定
5. 返回 JSON 格式的计划

**返回格式**:
```json
{{
  "reasoning": "规划推理过程",
  "steps": [
    {{
      "step_id": 1,
      "description": "步骤描述",
      "tool": "工具名称或null",
      "tool_args": {{"arg1": "value1"}},
      "depends_on": []
    }},
    ...
  ]
}}
```

请直接返回 JSON，不要有其他内容。
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM API

        Args:
            prompt: 提示词

        Returns:
            LLM 响应
        """
        # TODO: 实现真实的 LLM 调用
        # 这里是一个模拟实现
        logger.info("Calling LLM for planning...")

        # 模拟响应
        mock_response = """
{
  "reasoning": "任务需要先搜索信息，然后基于搜索结果回答问题",
  "steps": [
    {
      "step_id": 1,
      "description": "搜索相关信息",
      "tool": "search",
      "tool_args": {"query": "从任务中提取的搜索关键词"},
      "depends_on": []
    },
    {
      "step_id": 2,
      "description": "基于搜索结果生成答案",
      "tool": null,
      "tool_args": {},
      "depends_on": [1]
    }
  ]
}
"""
        return mock_response

    def _parse_llm_response(self, response: str, task: str) -> Plan:
        """
        解析 LLM 响应

        Args:
            response: LLM 响应字符串
            task: 原始任务

        Returns:
            Plan 对象
        """
        try:
            # 尝试提取 JSON（可能被 markdown 代码块包裹）
            response = response.strip()
            if response.startswith("```"):
                # 移除 markdown 代码块
                lines = response.split("\n")
                json_lines = []
                in_json = False
                for line in lines:
                    if line.startswith("```"):
                        in_json = not in_json
                        continue
                    if in_json:
                        json_lines.append(line)
                response = "\n".join(json_lines)

            # 解析 JSON
            data = json.loads(response)

            # 构建 Plan
            steps = [Step(**step_data) for step_data in data.get("steps", [])]

            return Plan(
                task=task,
                steps=steps,
                reasoning=data.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # 返回降级计划
            return Plan(
                task=task,
                steps=[
                    Step(
                        step_id=1,
                        description=f"完成任务: {task}",
                        tool=None,
                        tool_args={},
                        depends_on=[],
                    )
                ],
                reasoning="解析失败，使用降级计划",
            )

    def _heuristic_plan(self, task: str, available_tools: List[dict]) -> Plan:
        """
        启发式规划（不使用 LLM）

        Args:
            task: 任务描述
            available_tools: 可用工具列表

        Returns:
            Plan 对象
        """
        steps = []

        # 启发式规则 1: 如果任务包含搜索相关词汇，添加搜索步骤
        search_keywords = ["搜索", "查找", "search", "find", "最新", "新闻"]
        if any(keyword in task.lower() for keyword in search_keywords):
            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    description="搜索相关信息",
                    tool="search",
                    tool_args={"query": task},
                    depends_on=[],
                )
            )

        # 启发式规则 2: 如果任务包含知识库相关词汇，添加知识库查询
        kb_keywords = ["公司", "文档", "政策", "规定", "knowledge"]
        if any(keyword in task.lower() for keyword in kb_keywords):
            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    description="查询知识库",
                    tool="knowledge_base",
                    tool_args={"query": task},
                    depends_on=[],
                )
            )

        # 启发式规则 3: 如果任务包含天气相关词汇，添加天气查询
        weather_keywords = ["天气", "weather", "气温", "temperature"]
        if any(keyword in task.lower() for keyword in weather_keywords):
            # 尝试提取城市名称
            import re

            city_pattern = r"(北京|上海|深圳|广州|杭州|成都|武汉|西安|南京|重庆|天津|苏州|长沙|郑州|沈阳|青岛|大连|厦门|福州|济南|合肥|南昌|昆明|贵阳|兰州|太原|石家庄|哈尔滨|长春|乌鲁木齐|拉萨|西宁|呼和浩特|银川|海口|南宁|香港|澳门|台北)"
            match = re.search(city_pattern, task)
            city = match.group(1) if match else "北京"

            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    description=f"查询{city}天气",
                    tool="weather",
                    tool_args={"city": city},
                    depends_on=[],
                )
            )

        # 启发式规则 4: 如果任务包含计算相关词汇，添加计算器
        calc_keywords = ["计算", "算", "多少", "=", "+", "-", "*", "/"]
        if any(keyword in task for keyword in calc_keywords):
            # 尝试提取数学表达式
            import re

            expr_pattern = r"(\d+[\+\-\*/]\d+)"
            match = re.search(expr_pattern, task)
            expression = match.group(1) if match else "1+1"

            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    description="执行计算",
                    tool="calculator",
                    tool_args={"expression": expression},
                    depends_on=[],
                )
            )

        # 如果没有匹配到任何规则，添加一个通用步骤
        if not steps:
            steps.append(
                Step(
                    step_id=1,
                    description=f"完成任务: {task}",
                    tool=None,
                    tool_args={},
                    depends_on=[],
                )
            )

        # 添加最终合成步骤
        steps.append(
            Step(
                step_id=len(steps) + 1,
                description="综合所有结果，生成最终答案",
                tool=None,
                tool_args={},
                depends_on=[step.step_id for step in steps],
            )
        )

        return Plan(
            task=task, steps=steps, reasoning="基于启发式规则生成的计划"
        )

    async def replan(
        self,
        original_plan: Plan,
        failed_step: Step,
        error_message: str,
        execution_results: dict,
    ) -> Plan:
        """
        重新规划（当某个步骤失败时）

        Args:
            original_plan: 原始计划
            failed_step: 失败的步骤
            error_message: 错误信息
            execution_results: 已执行步骤的结果

        Returns:
            新的 Plan 对象
        """
        logger.warning(
            f"Replanning due to step {failed_step.step_id} failure: {error_message}"
        )

        try:
            # 移除失败步骤及其后续步骤
            new_steps = [
                step
                for step in original_plan.steps
                if step.step_id < failed_step.step_id
            ]

            # 添加一个恢复步骤（尝试使用不同工具或参数）
            recovery_step = Step(
                step_id=len(new_steps) + 1,
                description=f"恢复步骤: {failed_step.description}（使用替代方案）",
                tool=failed_step.tool,
                tool_args=failed_step.tool_args,
                depends_on=[],
            )
            new_steps.append(recovery_step)

            # 添加最终合成步骤
            new_steps.append(
                Step(
                    step_id=len(new_steps) + 1,
                    description="综合所有结果，生成最终答案",
                    tool=None,
                    tool_args={},
                    depends_on=[step.step_id for step in new_steps],
                )
            )

            return Plan(
                task=original_plan.task,
                steps=new_steps,
                reasoning=f"由于步骤 {failed_step.step_id} 失败而重新规划: {error_message}",
            )

        except Exception as e:
            logger.error(f"Replanning failed: {e}")
            # 返回简化计划
            return Plan(
                task=original_plan.task,
                steps=[
                    Step(
                        step_id=1,
                        description=f"完成任务: {original_plan.task}",
                        tool=None,
                        tool_args={},
                        depends_on=[],
                    )
                ],
                reasoning="重新规划失败，使用降级计划",
            )
