"""
ReAct Agent 引擎 - Iter 4

实现 Reason + Act 推理引擎，支持多步骤推理与工具调用。

参考:
- ReAct Paper: https://arxiv.org/abs/2210.03629
- LangChain Agent: https://python.langchain.com/docs/modules/agents/
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# ==================== 类型定义 ====================


class ThoughtType(Enum):
    """思考类型"""

    REASONING = "reasoning"  # 推理
    ACTION = "action"  # 行动
    OBSERVATION = "observation"  # 观察
    FINAL_ANSWER = "final_answer"  # 最终答案


@dataclass
class Action:
    """工具调用行动"""

    tool_name: str
    params: Dict[str, Any]


@dataclass
class Thought:
    """Agent 思考"""

    type: ThoughtType
    content: str
    action: Optional[Action] = None
    is_final: bool = False
    answer: Optional[str] = None


@dataclass
class AgentStep:
    """推理步骤"""

    step_num: int
    thought: Thought
    action: Optional[Action]
    observation: Optional[str]


@dataclass
class AgentResult:
    """Agent 执行结果"""

    answer: str
    steps: List[AgentStep]
    total_iterations: int
    success: bool
    error: Optional[str] = None


# ==================== 工具协议 ====================


class Tool(Protocol):
    """工具接口协议"""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Args:
            params: 工具参数

        Returns:
            执行结果
        """
        ...


# ==================== ReAct Agent ====================


class ReactAgent:
    """
    ReAct (Reason + Act) Agent 引擎

    推理循环:
    1. Thought: 分析当前状态，决定下一步
    2. Action: 调用工具执行
    3. Observation: 观察执行结果
    4. ... (循环)
    5. Final Answer: 给出最终答案
    """

    def __init__(
        self,
        llm_client,
        tools: List[Tool],
        max_iterations: int = 10,
        timeout_seconds: int = 30,
    ):
        """
        初始化 ReAct Agent

        Args:
            llm_client: LLM 客户端
            tools: 可用工具列表
            max_iterations: 最大迭代次数
            timeout_seconds: 超时时间
        """
        self.llm = llm_client
        self.tools = {tool.name: tool for tool in tools}
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds

        logger.info(f"ReAct Agent initialized with {len(tools)} tools: {list(self.tools.keys())}")

    async def solve(self, query: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        解决查询

        Args:
            query: 用户查询
            context: 上下文信息（可选）

        Returns:
            执行结果
        """
        logger.info(f"ReAct Agent solving: {query[:100]}...")

        history: List[AgentStep] = []
        context = context or {}

        try:
            # 设置超时
            return await asyncio.wait_for(
                self._reasoning_loop(query, context, history),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(f"ReAct Agent timeout after {self.timeout_seconds}s")
            return AgentResult(
                answer="抱歉，问题处理超时，请稍后再试。",
                steps=history,
                total_iterations=len(history),
                success=False,
                error="timeout",
            )
        except Exception as e:
            logger.error(f"ReAct Agent failed: {e}", exc_info=True)
            return AgentResult(
                answer=f"抱歉，处理过程中出现错误：{str(e)}",
                steps=history,
                total_iterations=len(history),
                success=False,
                error=str(e),
            )

    async def _reasoning_loop(
        self, query: str, context: Dict[str, Any], history: List[AgentStep]
    ) -> AgentResult:
        """推理循环"""

        for i in range(self.max_iterations):
            logger.info(f"ReAct iteration {i + 1}/{self.max_iterations}")

            # 1. 推理：决定下一步行动
            thought = await self._reason(query, context, history)

            # 2. 检查是否得到最终答案
            if thought.is_final:
                logger.info(f"ReAct converged after {i + 1} iterations")
                return AgentResult(
                    answer=thought.answer or "",
                    steps=history,
                    total_iterations=i + 1,
                    success=True,
                )

            # 3. 执行工具
            if thought.action:
                try:
                    observation = await self._execute_tool(thought.action)
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    observation = f"工具执行失败：{str(e)}"
            else:
                observation = "未选择任何工具"

            # 4. 记录步骤
            history.append(
                AgentStep(
                    step_num=i + 1,
                    thought=thought,
                    action=thought.action,
                    observation=observation,
                )
            )

        # 未能在最大迭代次数内收敛
        logger.warning(f"ReAct did not converge after {self.max_iterations} iterations")
        return AgentResult(
            answer="抱歉，问题过于复杂，未能在限定时间内完成。",
            steps=history,
            total_iterations=self.max_iterations,
            success=False,
            error="max_iterations_reached",
        )

    async def _reason(
        self, query: str, context: Dict[str, Any], history: List[AgentStep]
    ) -> Thought:
        """
        推理：分析当前状态，决定下一步行动

        Args:
            query: 用户查询
            context: 上下文
            history: 历史步骤

        Returns:
            思考结果
        """
        # 构建提示词
        prompt = self._build_reasoning_prompt(query, context, history)

        # 调用 LLM
        response = await self.llm.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )

        reasoning_text = response.choices[0].message.content

        # 解析 LLM 输出
        thought = self._parse_reasoning(reasoning_text)

        logger.debug(f"Reasoning: {thought.content[:100]}")
        return thought

    def _build_reasoning_prompt(
        self, query: str, context: Dict[str, Any], history: List[AgentStep]
    ) -> str:
        """构建推理提示词"""

        # 工具描述
        tools_desc = "\n".join(
            [
                f"- {name}: {tool.description}\n  参数: {tool.parameters}"
                for name, tool in self.tools.items()
            ]
        )

        # 历史步骤
        history_text = ""
        if history:
            history_text = "\n".join(
                [
                    f"步骤 {step.step_num}:\n"
                    f"  思考: {step.thought.content}\n"
                    f"  行动: {step.action.tool_name if step.action else '无'}\n"
                    f"  观察: {step.observation}"
                    for step in history
                ]
            )

        prompt = f"""你是一个智能助手，可以通过推理和调用工具来回答问题。

【问题】
{query}

【可用工具】
{tools_desc}

【历史步骤】
{history_text if history_text else "（暂无）"}

【推理规则】
1. 仔细分析问题，决定下一步行动
2. 如果需要外部信息或计算，选择合适的工具
3. 如果已经可以回答问题，输出最终答案
4. 每次只执行一个工具

【输出格式】
思考: <你的推理过程>
行动: <工具名称>
参数: <JSON 格式参数>

或者（如果可以回答）：
思考: <推理过程>
最终答案: <答案>

请开始推理：
"""
        return prompt

    def _parse_reasoning(self, text: str) -> Thought:
        """
        解析 LLM 推理输出

        支持格式:
        1. 思考: ... 行动: tool_name 参数: {...}
        2. 思考: ... 最终答案: ...
        """
        text = text.strip()

        # 解析思考
        if "思考:" in text:
            thinking = text.split("思考:")[1].split("\n")[0].strip()
        else:
            thinking = text.split("\n")[0]

        # 检查是否为最终答案
        if "最终答案:" in text:
            answer = text.split("最终答案:")[1].strip()
            return Thought(
                type=ThoughtType.FINAL_ANSWER,
                content=thinking,
                is_final=True,
                answer=answer,
            )

        # 解析行动和参数
        if "行动:" in text and "参数:" in text:
            action_line = text.split("行动:")[1].split("\n")[0].strip()
            tool_name = action_line.strip()

            params_text = text.split("参数:")[1].strip()
            try:
                import json

                params = json.loads(params_text)
            except Exception as e:
                logger.warning(f"Failed to parse params: {e}")
                params = {}

            return Thought(
                type=ThoughtType.ACTION,
                content=thinking,
                action=Action(tool_name=tool_name, params=params),
            )

        # 默认返回推理类型
        return Thought(type=ThoughtType.REASONING, content=thinking)

    async def _execute_tool(self, action: Action) -> str:
        """
        执行工具

        Args:
            action: 工具行动

        Returns:
            执行结果（文本描述）
        """
        tool_name = action.tool_name
        params = action.params

        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]

        logger.info(f"Executing tool: {tool_name} with params: {params}")

        try:
            result = await tool.execute(params)

            # 将结果转为文本描述
            if isinstance(result, dict):
                if "text" in result:
                    return result["text"]
                elif "result" in result:
                    return str(result["result"])
                else:
                    return str(result)
            else:
                return str(result)

        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            raise


# ==================== 工具注册表 ====================


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"Tool registered: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())


# 全局工具注册表
tool_registry = ToolRegistry()
