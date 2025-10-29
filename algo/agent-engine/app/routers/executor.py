"""
Executor API - 执行器 API

提供 Plan-Execute 执行器的 REST API 接口
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.executors.plan_execute_executor import (
    ExecutionTrace,
    get_plan_execute_executor,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/executor", tags=["Executor"])


class ExecuteTaskRequest(BaseModel):
    """执行任务请求"""

    task: str = Field(..., description="任务描述")
    context: dict | None = Field(None, description="上下文信息")


class ExecuteTaskResponse(BaseModel):
    """执行任务响应"""

    task: str = Field(..., description="任务描述")
    success: bool = Field(..., description="是否成功")
    final_answer: str = Field(..., description="最终答案")
    plan: dict = Field(..., description="执行计划")
    step_results: list = Field(..., description="步骤结果")
    total_time_ms: float = Field(..., description="总执行时长（毫秒）")


@router.post("/execute", response_model=ExecuteTaskResponse, summary="执行复杂任务")
async def execute_task(request: ExecuteTaskRequest):
    """
    使用 Plan-Execute 模式执行复杂任务

    **流程**:
    1. **规划**: 使用 LLM 将任务分解为多个步骤
    2. **执行**: 逐步执行每个步骤，调用相应工具
    3. **综合**: 综合所有步骤结果，生成最终答案

    **特性**:
    - ✅ 自动任务分解
    - ✅ 步骤依赖管理
    - ✅ 失败重试机制
    - ✅ 完整执行追踪

    **示例任务**:
    - "搜索最新的 Python 编程资讯，并总结要点"
    - "查询北京今天的天气，如果下雨提醒带伞"
    - "计算 (100 + 50) * 2 的结果"
    - "搜索公司最新的休假政策"

    Args:
        task: 任务描述
        context: 可选的上下文信息

    Returns:
        执行结果，包含计划、步骤结果和最终答案
    """
    try:
        logger.info(f"Executing task: {request.task}")

        # 获取执行器
        executor = get_plan_execute_executor()

        # 执行任务
        trace: ExecutionTrace = await executor.execute(
            task=request.task, context=request.context
        )

        logger.info(
            f"Task completed: success={trace.success}, time={trace.total_time_ms:.2f}ms"
        )

        # 转换为响应格式
        return ExecuteTaskResponse(
            task=trace.task,
            success=trace.success,
            final_answer=trace.final_answer,
            plan=trace.plan.dict(),
            step_results=[result.dict() for result in trace.step_results],
            total_time_ms=trace.total_time_ms,
        )

    except Exception as e:
        logger.error(f"Task execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Task execution failed: {str(e)}"
        )


class PlanTaskRequest(BaseModel):
    """规划任务请求"""

    task: str = Field(..., description="任务描述")
    context: dict | None = Field(None, description="上下文信息")


@router.post("/plan", summary="生成任务执行计划（不执行）")
async def plan_task(request: PlanTaskRequest):
    """
    仅生成任务执行计划，不实际执行

    用于预览任务将如何被分解和执行

    Args:
        task: 任务描述
        context: 可选的上下文信息

    Returns:
        执行计划
    """
    try:
        logger.info(f"Planning task: {request.task}")

        # 获取执行器
        executor = get_plan_execute_executor()

        # 获取可用工具
        available_tools = executor._get_available_tools()

        # 生成计划
        plan = await executor.planner.create_plan(
            task=request.task, available_tools=available_tools, context=request.context
        )

        logger.info(f"Plan created: {len(plan.steps)} steps")

        return plan.dict()

    except Exception as e:
        logger.error(f"Task planning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Task planning failed: {str(e)}"
        )


@router.get("/status", summary="获取执行器状态")
async def get_executor_status():
    """
    获取 Plan-Execute 执行器的状态

    Returns:
        执行器状态信息
    """
    try:
        executor = get_plan_execute_executor()

        # 获取工具注册表状态
        tools = executor.tool_registry.list_tools()

        return {
            "executor_type": "plan_execute",
            "max_retries": executor.max_retries,
            "available_tools": len(tools),
            "tool_names": [tool["name"] for tool in tools],
            "llm_configured": executor.llm_client is not None,
            "status": "healthy",
        }

    except Exception as e:
        logger.error(f"Failed to get executor status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
