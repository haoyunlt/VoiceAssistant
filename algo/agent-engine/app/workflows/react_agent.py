"""
ReAct Agent 工作流实现
基于 LangGraph 的 ReAct (Reasoning + Acting) 模式
"""

import logging
import operator
from typing import Annotated, Any, TypedDict

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.memory.memory_manager import MemoryManager
from app.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


# 定义 Agent 状态
class AgentState(TypedDict):
    """Agent 状态"""

    messages: Annotated[list[Any], operator.add]  # 消息历史
    iteration: int  # 当前迭代次数
    max_iterations: int  # 最大迭代次数
    tools_called: list[str]  # 已调用的工具
    final_answer: str | None  # 最终答案
    error: str | None  # 错误信息


class ReActAgent:
    """ReAct Agent（推理 + 行动）"""

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_iterations: int = 5,
        verbose: bool = False,
    ):
        """
        初始化 ReAct Agent

        Args:
            model: LLM 模型名称
            temperature: 温度参数
            max_iterations: 最大迭代次数
            verbose: 是否输出详细日志
        """
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.verbose = verbose

        # 初始化 LLM
        self.llm = ChatOpenAI(model=model, temperature=temperature)

        # 初始化工具注册表
        self.tool_registry = ToolRegistry()

        # 初始化记忆管理器
        self.memory_manager = MemoryManager()

        # 初始化工作流
        self.workflow = self._build_workflow()

        logger.info(f"ReAct Agent initialized: model={model}, max_iterations={max_iterations}")

    def _build_workflow(self) -> StateGraph:
        """构建 LangGraph 工作流"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("executor", self._executor_node)
        workflow.add_node("reflector", self._reflector_node)

        # 设置入口点
        workflow.set_entry_point("planner")

        # 添加边
        workflow.add_edge("planner", "executor")
        workflow.add_conditional_edges(
            "executor", self._should_continue, {"continue": "reflector", "end": END}
        )
        workflow.add_edge("reflector", "planner")

        return workflow.compile()

    def _planner_node(self, state: AgentState) -> AgentState:
        """
        Planner 节点：思考下一步行动

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Planner node (iteration {state['iteration']})")

        # 构造系统提示
        system_prompt = self._build_system_prompt()

        # 构造消息列表
        messages = [SystemMessage(content=system_prompt)] + state["messages"]

        # 调用 LLM
        response = self.llm.invoke(messages)

        # 解析响应
        plan = self._parse_plan(response.content)

        if self.verbose:
            logger.info(f"Plan: {plan}")

        # 更新状态
        state["messages"].append(AIMessage(content=response.content))

        return state

    def _executor_node(self, state: AgentState) -> AgentState:
        """
        Executor 节点：执行工具调用

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Executor node (iteration {state['iteration']})")

        # 从最后一条 AI 消息中提取工具调用
        last_message = state["messages"][-1]

        if not isinstance(last_message, AIMessage):
            return state

        # 解析工具调用
        tool_calls = self._parse_tool_calls(last_message.content)

        if not tool_calls:
            # 没有工具调用，可能是最终答案
            final_answer = self._extract_final_answer(last_message.content)
            if final_answer:
                state["final_answer"] = final_answer
            return state

        # 执行工具调用
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            logger.info(f"Calling tool: {tool_name}({tool_args})")

            try:
                # 执行工具
                result = self.tool_registry.execute_tool(tool_name, tool_args)

                # 记录工具调用
                state["tools_called"].append(tool_name)

                # 添加工具结果到消息
                state["messages"].append(
                    HumanMessage(content=f"Tool '{tool_name}' result: {result}")
                )

                if self.verbose:
                    logger.info(f"Tool result: {result}")

            except Exception as e:
                error_msg = f"Tool '{tool_name}' failed: {str(e)}"
                logger.error(error_msg)
                state["messages"].append(HumanMessage(content=error_msg))
                state["error"] = error_msg

        return state

    def _reflector_node(self, state: AgentState) -> AgentState:
        """
        Reflector 节点：反思和评估

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.debug(f"Reflector node (iteration {state['iteration']})")

        # 增加迭代计数
        state["iteration"] += 1

        # 检查是否达到最大迭代次数
        if state["iteration"] >= state["max_iterations"]:
            logger.warning(f"Max iterations ({state['max_iterations']}) reached")
            state["final_answer"] = "Maximum iterations reached. Could not complete the task."

        return state

    def _should_continue(self, state: AgentState) -> str:
        """
        判断是否继续

        Args:
            state: 当前状态

        Returns:
            "continue" 或 "end"
        """
        # 如果有最终答案，结束
        if state.get("final_answer"):
            return "end"

        # 如果有错误，结束
        if state.get("error"):
            return "end"

        # 如果达到最大迭代次数，结束
        if state["iteration"] >= state["max_iterations"]:
            return "end"

        return "continue"

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        tools_desc = self.tool_registry.get_tools_description()

        prompt = f"""You are a helpful AI assistant with access to tools.

Available tools:
{tools_desc}

When you need to use a tool, use the following format:
Action: <tool_name>
Action Input: <tool_arguments>

When you have the final answer, use:
Final Answer: <your answer>

Think step by step and use tools when necessary.
"""
        return prompt

    def _parse_plan(self, content: str) -> dict[str, Any]:
        """解析计划"""
        # 简化版：提取 Action 和 Action Input
        plan = {}

        if "Action:" in content:
            lines = content.split("\n")
            for _i, line in enumerate(lines):
                if line.startswith("Action:"):
                    plan["action"] = line.replace("Action:", "").strip()
                if line.startswith("Action Input:"):
                    plan["input"] = line.replace("Action Input:", "").strip()

        return plan

    def _parse_tool_calls(self, content: str) -> list[dict[str, Any]]:
        """解析工具调用"""
        tool_calls = []

        lines = content.split("\n")
        action = None
        action_input = None

        for line in lines:
            if line.startswith("Action:"):
                action = line.replace("Action:", "").strip()
            elif line.startswith("Action Input:"):
                action_input = line.replace("Action Input:", "").strip()

                if action and action_input:
                    tool_calls.append(
                        {
                            "name": action,
                            "args": {"query": action_input},  # 简化版
                        }
                    )
                    action = None
                    action_input = None

        return tool_calls

    def _extract_final_answer(self, content: str) -> str | None:
        """提取最终答案"""
        if "Final Answer:" in content:
            return content.split("Final Answer:")[1].strip()
        return None

    def run(
        self,
        user_input: str,
        conversation_id: str | None = None,
        _context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        运行 Agent

        Args:
            user_input: 用户输入
            conversation_id: 对话 ID
            context: 上下文信息

        Returns:
            执行结果
        """
        logger.info(f"Running ReAct Agent: {user_input[:100]}...")

        # 初始化状态
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_input)],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "tools_called": [],
            "final_answer": None,
            "error": None,
        }

        # 如果有对话 ID，加载记忆
        if conversation_id:
            memory = self.memory_manager.load_memory(conversation_id)
            if memory:
                initial_state["messages"] = memory + initial_state["messages"]

        # 运行工作流
        try:
            final_state = self.workflow.invoke(initial_state)

            # 保存记忆
            if conversation_id:
                self.memory_manager.save_memory(conversation_id, final_state["messages"])

            # 构造响应
            result = {
                "answer": final_state.get("final_answer", "No answer generated"),
                "iterations": final_state["iteration"],
                "tools_called": final_state["tools_called"],
                "success": final_state.get("error") is None,
                "error": final_state.get("error"),
            }

            logger.info(
                f"Agent completed: {result['iterations']} iterations, {len(result['tools_called'])} tools called"
            )

            return result

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return {
                "answer": f"Error: {str(e)}",
                "iterations": 0,
                "tools_called": [],
                "success": False,
                "error": str(e),
            }

    def stream(
        self,
        user_input: str,
        conversation_id: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        """
        流式运行 Agent

        Args:
            user_input: 用户输入
            conversation_id: 对话 ID
            context: 上下文信息

        Yields:
            执行过程中的事件
        """
        # TODO: 实现流式输出
        result = self.run(user_input, conversation_id, context)
        yield result
