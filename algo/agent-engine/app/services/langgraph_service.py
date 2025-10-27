"""
LangGraph 工作流服务
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.langgraph_workflow import LangGraphWorkflow

logger = logging.getLogger(__name__)


class LangGraphService:
    """LangGraph工作流服务"""

    def __init__(
        self,
        llm_service,
        tool_service,
        max_iterations: int = 10,
    ):
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
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
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
            max_iterations=max_iterations,
        )

        logger.info(
            f"Task completed: success={result['success']}, "
            f"iterations={result['iterations']}"
        )

        return result
