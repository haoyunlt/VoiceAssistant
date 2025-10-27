"""Agent执行路由"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.agent import AgentResult, AgentTask
from app.services.agent_service import AgentService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
agent_service = AgentService()

# LangGraph 服务实例（延迟初始化）
langgraph_service = None


class ExecuteAgentRequest(BaseModel):
    """Agent执行请求"""
    task: str = Field(..., description="任务描述")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息")
    tools: Optional[List[str]] = Field(default=None, description="可用工具列表")
    max_iterations: Optional[int] = Field(default=10, description="最大迭代次数")
    model: Optional[str] = Field(default=None, description="使用的模型")


class ExecuteAgentResponse(BaseModel):
    """Agent执行响应"""
    task_id: str
    result: str
    steps: List[Dict[str, Any]]
    status: str
    iterations: int
    execution_time: float
    metadata: Dict[str, Any]


@router.post("/execute", response_model=ExecuteAgentResponse)
async def execute_agent(request: ExecuteAgentRequest):
    """
    执行Agent任务

    Agent会根据任务描述，自主决策使用哪些工具，
    进行多步推理，最终完成任务。
    """
    try:
        logger.info(f"Executing agent task: {request.task[:100]}...")

        # 创建Agent任务
        task = AgentTask(
            task=request.task,
            context=request.context or {},
            tools=request.tools or [],
            max_iterations=request.max_iterations or 10,
            model=request.model,
        )

        # 执行Agent
        result = await agent_service.execute(task)

        return ExecuteAgentResponse(
            task_id=result.task_id,
            result=result.result,
            steps=result.steps,
            status=result.status,
            iterations=result.iterations,
            execution_time=result.execution_time,
            metadata=result.metadata,
        )

    except Exception as e:
        logger.error(f"Failed to execute agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-async")
async def execute_agent_async(
    request: ExecuteAgentRequest,
    background_tasks: BackgroundTasks,
):
    """
    异步执行Agent任务

    立即返回task_id，任务在后台执行
    """
    task_id = agent_service.generate_task_id()

    # 添加后台任务
    task = AgentTask(
        task_id=task_id,
        task=request.task,
        context=request.context or {},
        tools=request.tools or [],
        max_iterations=request.max_iterations or 10,
        model=request.model,
    )

    background_tasks.add_task(agent_service.execute_async, task)

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task submitted successfully",
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    result = await agent_service.get_task_result(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return result

# 任务管理相关的新端点

@router.get("/tasks/{task_id}", response_model=AgentResult, summary="获取任务结果")
async def get_task_result(task_id: str):
    """
    从Redis获取任务执行结果

    Args:
        task_id: 任务ID

    Returns:
        任务执行结果
    """
    from app.services.task_manager import task_manager

    result = await task_manager.get_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return result


@router.get("/tasks", summary="列出任务")
async def list_tasks(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None
):
    """
    列出任务（按创建时间倒序）

    Args:
        limit: 返回数量限制
        offset: 偏移量
        status: 状态过滤（可选）

    Returns:
        任务列表
    """
    from app.models.agent import AgentStatus
    from app.services.task_manager import task_manager

    status_filter = None
    if status:
        try:
            status_filter = AgentStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    results = await task_manager.list_tasks(
        limit=limit,
        offset=offset,
        status=status_filter
    )

    return {
        "total": len(results),
        "limit": limit,
        "offset": offset,
        "tasks": results
    }


@router.get("/tasks/stats/summary", summary="获取任务统计")
async def get_task_stats():
    """
    获取任务统计信息

    Returns:
        统计信息字典
    """
    from app.services.task_manager import task_manager

    stats = await task_manager.get_task_stats()
    return stats


@router.delete("/tasks/{task_id}", summary="删除任务")
async def delete_task(task_id: str):
    """
    删除指定任务

    Args:
        task_id: 任务ID

    Returns:
        删除结果
    """
    from app.services.task_manager import task_manager

    success = await task_manager.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete task")

    return {"success": True, "message": f"Task {task_id} deleted"}


@router.post("/tasks/cleanup", summary="清理旧任务")
async def cleanup_old_tasks(days: int = 7):
    """
    清理超过指定天数的旧任务

    Args:
        days: 天数阈值（默认7天）

    Returns:
        清理结果
    """
    from app.services.task_manager import task_manager

    deleted_count = await task_manager.cleanup_old_tasks(days=days)

    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"Cleaned up {deleted_count} tasks older than {days} days"
    }


class LangGraphExecuteRequest(BaseModel):
    """LangGraph工作流执行请求"""

    task: str = Field(..., description="任务描述")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息")
    tools: Optional[List[str]] = Field(default=None, description="可用工具列表")
    max_iterations: Optional[int] = Field(default=10, description="最大迭代次数")


class LangGraphExecuteResponse(BaseModel):
    """LangGraph工作流执行响应"""

    success: bool
    final_result: str
    execution_results: List[Dict[str, Any]]
    iterations: int
    error: Optional[str]


@router.post("/execute-stream")
async def execute_agent_stream(request: ExecuteAgentRequest):
    """
    流式执行Agent任务 (Server-Sent Events)

    实时返回Agent执行的每个步骤，包括：
    - Thought（思考）
    - Action（工具调用）
    - Observation（工具结果）
    - Answer（最终答案）

    事件格式 (SSE):
    ```
    event: thought
    data: {"step_number": 1, "content": "...", "timestamp": "..."}

    event: action
    data: {"step_number": 2, "tool_name": "search", "content": "..."}

    event: observation
    data: {"step_number": 3, "content": "...", "tool_name": "search"}

    event: answer
    data: {"step_number": 4, "content": "Final answer here"}

    event: complete
    data: {"task_id": "...", "iterations": 3, "execution_time": 5.2}
    ```

    使用方式:
    ```javascript
    const eventSource = new EventSource('/api/v1/agent/execute-stream');

    eventSource.addEventListener('thought', (e) => {
        const data = JSON.parse(e.data);
        console.log('Thought:', data.content);
    });

    eventSource.addEventListener('answer', (e) => {
        const data = JSON.parse(e.data);
        console.log('Final Answer:', data.content);
    });

    eventSource.addEventListener('complete', (e) => {
        console.log('Completed');
        eventSource.close();
    });
    ```
    """
    try:
        logger.info(f"Starting streaming execution: {request.task[:100]}...")

        # 创建Agent任务
        task = AgentTask(
            task=request.task,
            context=request.context or {},
            tools=request.tools or [],
            max_iterations=request.max_iterations or 10,
            model=request.model,
        )

        # 流式生成函数
        async def event_generator():
            try:
                async for event in agent_service.execute_stream(task):
                    event_type = event.get("event_type", "message")

                    # Server-Sent Events 格式
                    yield f"event: {event_type}\n"
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    # 确保立即发送
                    await asyncio.sleep(0)

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_event = {
                    "event_type": "error",
                    "error": str(e),
                }
                yield f"event: error\n"
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            },
        )

    except Exception as e:
        logger.error(f"Failed to start streaming execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-langgraph", response_model=LangGraphExecuteResponse)
async def execute_with_langgraph(request: LangGraphExecuteRequest):
    """
    使用LangGraph工作流执行任务

    LangGraph实现4节点状态机循环:
    - Planner: 任务规划分解
    - Executor: 执行具体步骤
    - Critic: 反思与验证
    - Synthesizer: 综合最终结果

    特性:
    - 自动状态管理
    - 条件边动态路由
    - 支持重新规划
    - 最大迭代控制

    示例:
    ```json
    {
        "task": "搜索最近的天气，然后建议穿衣",
        "tools": ["web_search"],
        "max_iterations": 10
    }
    ```
    """
    global langgraph_service

    try:
        # 延迟初始化LangGraph服务
        if langgraph_service is None:
            logger.info("Initializing LangGraph service...")
            from app.services.langgraph_service import LangGraphService
            from app.services.llm_service import LLMService
            from app.services.tool_service import ToolService

            llm_service = LLMService()
            tool_service = ToolService()
            langgraph_service = LangGraphService(
                llm_service=llm_service,
                tool_service=tool_service,
                max_iterations=10,
            )

        logger.info(f"Executing task with LangGraph: {request.task[:100]}")

        result = await langgraph_service.execute_task(
            task=request.task,
            context=request.context,
            tools=request.tools,
            max_iterations=request.max_iterations,
        )

        return LangGraphExecuteResponse(**result)

    except Exception as e:
        logger.error(f"LangGraph execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
