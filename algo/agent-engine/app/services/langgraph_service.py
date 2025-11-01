"""
LangGraph 工作流服务
"""

import logging
from typing import Any

from app.core.langgraph_workflow import LangGraphWorkflow
from app.services.llm_service import LLMService
from app.services.tool_service import ToolService

logger = logging.getLogger(__name__)


class LangGraphService:
    """LangGraph工作流服务"""

    def __init__(
        self,
        llm_service: LLMService,
        tool_service: ToolService,
        max_iterations: int = 10,
    ) -> None:
        """
        初始化LangGraph服务

        Args:
            llm_service: LLM服务
            tool_service: 工具服务
            max_iterations: 最大迭代次数
        """
        self.workflow = LangGraphWorkflow(
            llm_service=llm_service,
            tool_service=tool_service,
            max_iterations=max_iterations,
        )
        logger.info("LangGraphService initialized")

    async def execute_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        tools: list[str] | None = None,
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 上下文信息
            tools: 可用工具列表
            max_iterations: 最大迭代次数

        Returns:
            执行结果
        """
        logger.info(f"Executing task with LangGraph: {task[:100]}")

        result = await self.workflow.run(
            task=task,
            context=context,
            available_tools=tools,
            max_iterations=max_iterations if max_iterations else self.workflow.max_iterations,
        )  # type: ignore

        logger.info(
            f"Task completed: success={result['success']}, iterations={result['iterations']}"
        )

        return result
