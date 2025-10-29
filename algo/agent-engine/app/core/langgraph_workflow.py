"""
LangGraph 状态机工作流
实现 4 节点循环: Planner → Executor → Critic → Synthesizer
"""

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Agent状态定义"""

    # 输入
    task: str  # 原始任务描述
    context: dict[str, Any]  # 上下文信息
    available_tools: list[str]  # 可用工具列表

    # 中间状态
    plan: list[dict[str, Any]]  # 任务计划
    current_step: int  # 当前步骤
    execution_results: list[dict]  # 执行结果

    # 控制标志
    need_reflection: bool  # 是否需要反思
    need_replan: bool  # 是否需要重新规划
    iterations: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数

    # 输出
    final_result: str  # 最终结果
    error: str | None  # 错误信息


class LangGraphWorkflow:
    """LangGraph工作流"""

    def __init__(
        self,
        llm_service,
        tool_service,
        max_iterations: int = 10,
    ):
        """
        初始化LangGraph工作流

        Args:
            llm_service: LLM服务
            tool_service: 工具服务
            max_iterations: 最大迭代次数
        """
        self.llm = llm_service
        self.tools = tool_service
        self.max_iterations = max_iterations

        # 构建状态图
        self.graph = self._build_graph()
        self.app = self.graph.compile()

        logger.info("LangGraph workflow initialized")

    def _build_graph(self) -> StateGraph:
        """构建LangGraph状态图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("planner", self._planning_node)
        workflow.add_node("executor", self._execution_node)
        workflow.add_node("critic", self._reflection_node)
        workflow.add_node("synthesizer", self._synthesis_node)

        # 设置入口点
        workflow.set_entry_point("planner")

        # 添加条件边
        workflow.add_conditional_edges(
            "planner",
            self._should_execute,
            {"execute": "executor", "refine": "planner", "end": END},
        )

        workflow.add_conditional_edges(
            "executor",
            self._should_reflect,
            {"continue": "executor", "reflect": "critic", "synthesize": "synthesizer"},
        )

        workflow.add_edge("critic", "planner")
        workflow.add_edge("synthesizer", END)

        return workflow

    async def _planning_node(self, state: AgentState) -> dict:
        """
        规划节点 - 任务分解

        Args:
            state: 当前状态

        Returns:
            更新的状态字段
        """
        logger.info(f"[Planner] 迭代 {state['iterations']}")

        task = state["task"]
        context = state.get("context", {})
        available_tools = state.get("available_tools", [])

        # 构建规划提示
        tools_desc = self._get_tools_description(available_tools)

        planning_prompt = f"""
任务: {task}
上下文: {json.dumps(context, ensure_ascii=False, indent=2)}
可用工具: {tools_desc}

请将任务分解为具体的执行步骤。每个步骤包含:
1. step_number: 步骤编号
2. description: 步骤描述
3. tool: 需要使用的工具 (如果需要)
4. input: 工具输入参数
5. expected_output: 预期输出

返回JSON格式的计划列表。
示例:
[
  {{
    "step_number": 1,
    "description": "搜索相关信息",
    "tool": "web_search",
    "input": {{"query": "Python编程"}},
    "expected_output": "搜索结果列表"
  }}
]
"""

        try:
            # 调用LLM生成计划
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个任务规划专家"},
                    {"role": "user", "content": planning_prompt},
                ],
                temperature=0.7,
            )

            # 解析计划
            plan = self._parse_plan(response)

            return {
                "plan": plan,
                "current_step": 0,
                "iterations": state["iterations"] + 1,
                "need_replan": False,
            }

        except Exception as e:
            logger.error(f"Planning failed: {e}", exc_info=True)
            return {
                "plan": [],
                "error": f"Planning failed: {str(e)}",
                "need_replan": False,
            }

    async def _execution_node(self, state: AgentState) -> dict:
        """
        执行节点 - 执行当前步骤

        Args:
            state: 当前状态

        Returns:
            更新的状态字段
        """
        logger.info(f"[Executor] 执行步骤 {state['current_step']}")

        plan = state.get("plan", [])
        current_step = state["current_step"]
        execution_results = state.get("execution_results", [])

        if current_step >= len(plan):
            return {
                "current_step": current_step,
                "need_reflection": False,
            }

        step = plan[current_step]

        # 执行步骤
        try:
            result = await self._execute_step(step)

            execution_results.append(
                {
                    "step": current_step,
                    "description": step.get("description"),
                    "result": result,
                    "success": True,
                    "error": None,
                }
            )

            return {
                "current_step": current_step + 1,
                "execution_results": execution_results,
                "need_reflection": True,
            }

        except Exception as e:
            logger.error(f"步骤执行失败: {e}")
            execution_results.append(
                {
                    "step": current_step,
                    "result": None,
                    "success": False,
                    "error": str(e),
                }
            )

            return {
                "current_step": current_step,
                "execution_results": execution_results,
                "need_replan": True,
            }

    async def _reflection_node(self, state: AgentState) -> dict:
        """
        反思节点 - 验证执行结果

        Args:
            state: 当前状态

        Returns:
            更新的状态字段
        """
        logger.info("[Critic] 反思执行结果")

        execution_results = state.get("execution_results", [])
        plan = state.get("plan", [])

        reflection_prompt = f"""
计划: {json.dumps(plan, ensure_ascii=False, indent=2)}
执行结果: {json.dumps(execution_results, ensure_ascii=False, indent=2)}

请评估:
1. 执行结果是否符合预期?
2. 是否需要调整计划?
3. 下一步应该做什么?

返回JSON: {{"assessment": "评估", "need_replan": true/false, "reason": "原因"}}
"""

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个结果验证专家"},
                    {"role": "user", "content": reflection_prompt},
                ]
            )

            reflection = self._parse_reflection(response)

            return {"need_replan": reflection.get("need_replan", False)}

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return {"need_replan": False}

    async def _synthesis_node(self, state: AgentState) -> dict:
        """
        综合节点 - 生成最终结果

        Args:
            state: 当前状态

        Returns:
            更新的状态字段
        """
        logger.info("[Synthesizer] 综合最终结果")

        task = state["task"]
        execution_results = state.get("execution_results", [])

        synthesis_prompt = f"""
原始任务: {task}
执行结果: {json.dumps(execution_results, ensure_ascii=False, indent=2)}

请综合所有执行结果,生成完整的最终答案。
"""

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个信息综合专家"},
                    {"role": "user", "content": synthesis_prompt},
                ]
            )

            return {"final_result": response}

        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {"final_result": f"综合失败: {str(e)}"}

    def _should_execute(self, state: AgentState) -> str:
        """
        判断是否应该执行

        Args:
            state: 当前状态

        Returns:
            下一个节点名称
        """
        if state["iterations"] >= state["max_iterations"]:
            logger.warning("达到最大迭代次数")
            return "end"

        if state.get("need_replan", False):
            return "refine"

        if not state.get("plan") or len(state["plan"]) == 0:
            logger.warning("没有生成有效计划")
            return "end"

        return "execute"

    def _should_reflect(self, state: AgentState) -> str:
        """
        判断是否需要反思

        Args:
            state: 当前状态

        Returns:
            下一个节点名称
        """
        current_step = state.get("current_step", 0)
        plan = state.get("plan", [])
        need_reflection = state.get("need_reflection", False)

        # 所有步骤完成
        if current_step >= len(plan):
            return "synthesize"

        # 需要反思
        if need_reflection:
            return "reflect"

        # 继续执行
        return "continue"

    async def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        available_tools: list[str] | None = None,
        max_iterations: int = None,
    ) -> dict[str, Any]:
        """
        运行工作流

        Args:
            task: 任务描述
            context: 上下文信息
            available_tools: 可用工具列表
            max_iterations: 最大迭代次数

        Returns:
            执行结果
        """
        initial_state = {
            "task": task,
            "context": context or {},
            "available_tools": available_tools or [],
            "plan": [],
            "current_step": 0,
            "execution_results": [],
            "need_reflection": False,
            "need_replan": False,
            "iterations": 0,
            "max_iterations": max_iterations or self.max_iterations,
            "final_result": "",
            "error": None,
        }

        try:
            result = await self.app.ainvoke(initial_state)

            return {
                "success": True,
                "final_result": result.get("final_result", ""),
                "execution_results": result.get("execution_results", []),
                "iterations": result.get("iterations", 0),
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "final_result": "",
                "execution_results": [],
                "iterations": 0,
                "error": str(e),
            }

    async def _execute_step(self, step: dict[str, Any]) -> Any:
        """
        执行单个步骤

        Args:
            step: 步骤定义

        Returns:
            执行结果
        """
        tool_name = step.get("tool")
        tool_input = step.get("input", {})

        if not tool_name:
            # 无工具步骤，直接返回描述
            return step.get("description", "")

        # 调用工具
        result = await self.tools.execute_tool(tool_name, tool_input)
        return result

    def _get_tools_description(self, tool_names: list[str]) -> str:
        """
        获取工具描述

        Args:
            tool_names: 工具名称列表

        Returns:
            工具描述字符串
        """
        if not tool_names:
            return "无可用工具"

        descriptions = []
        for name in tool_names:
            tool_info = self.tools.get_tool_info(name)
            if tool_info:
                descriptions.append(f"- {name}: {tool_info.get('description', '')}")

        return "\n".join(descriptions) if descriptions else "无可用工具"

    def _parse_plan(self, response: str) -> list[dict[str, Any]]:
        """
        解析规划响应

        Args:
            response: LLM响应

        Returns:
            计划列表
        """
        try:
            # 尝试直接解析JSON
            plan = json.loads(response)
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON块
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group(1))
                if isinstance(plan, list):
                    return plan
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse plan, returning empty list")
        return []

    def _parse_reflection(self, response: str) -> dict[str, Any]:
        """
        解析反思响应

        Args:
            response: LLM响应

        Returns:
            反思结果
        """
        try:
            # 尝试直接解析JSON
            reflection = json.loads(response)
            if isinstance(reflection, dict):
                return reflection
        except json.JSONDecodeError:
            pass

        # 尝试提取JSON块
        import re

        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                reflection = json.loads(json_match.group(1))
                if isinstance(reflection, dict):
                    return reflection
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse reflection, returning default")
        return {"need_replan": False, "assessment": response}
