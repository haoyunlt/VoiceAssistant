"""
Multi-Agent 协作 API 路由
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore[import]
from pydantic import BaseModel, Field  # type: ignore[import]

from app.api.dependencies import get_agent_engine, get_tenant_id, verify_token
from app.core.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multi-agent", tags=["multi-agent"])


# 请求/响应模型
class CollaborateRequest(BaseModel):
    """协作请求"""

    task: str = Field(..., description="任务描述")
    mode: str = Field(
        default="parallel", description="协作模式: sequential/parallel/debate/voting/hierarchical"
    )
    agent_ids: list[str] | None = Field(
        default=None, description="参与的agent ID列表（未指定则自动选择）"
    )
    priority: int = Field(default=5, description="任务优先级（1-10）")


class CollaborateResponse(BaseModel):
    """协作响应"""

    task: str
    mode: str
    agents_involved: list[str]
    final_result: str | dict
    quality_score: float | None = None
    completion_time: float
    status: str
    metadata: dict[str, Any] = {}


class RegisterAgentRequest(BaseModel):
    """注册Agent请求"""

    agent_id: str
    role: str = Field(..., description="角色: coordinator/researcher/planner/executor/reviewer")
    tools: list[str] | None = Field(default=None, description="工具列表")


class RegisterAgentResponse(BaseModel):
    """注册Agent响应"""

    agent_id: str
    role: str
    message: str


class ListAgentsResponse(BaseModel):
    """列出Agents响应"""

    agents: list[dict[str, str]]
    count: int


class MultiAgentStatsResponse(BaseModel):
    """Multi-Agent统计响应"""

    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    avg_completion_time: float
    collaboration_quality_avg: float
    active_agents: int
    agent_load: dict[str, int]


@router.post("/collaborate", response_model=CollaborateResponse)
async def collaborate(
    request: CollaborateRequest,
    tenant_id: str = Depends(get_tenant_id),
    token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> CollaborateResponse:
    """
    执行Multi-Agent协作任务

    支持5种协作模式:
    - sequential: 串行执行
    - parallel: 并行执行
    - debate: 辩论模式（多轮讨论）
    - voting: 投票模式（多数决定）
    - hierarchical: 分层模式（coordinator分配给workers）
    """
    try:
        config = get_config()

        if not config.multi_agent_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Multi-agent feature is disabled",
            )

        if not hasattr(agent_engine, "multi_agent_coordinator"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Multi-agent coordinator not initialized",
            )

        from app.core.multi_agent.enhanced_coordinator import CollaborationMode

        # 验证模式
        try:
            mode = CollaborationMode(request.mode)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode: {request.mode}. Must be one of: sequential, parallel, debate, voting, hierarchical",
            )

        coordinator = agent_engine.multi_agent_coordinator

        # 执行协作
        result = await coordinator.collaborate(
            task=request.task,
            mode=mode,
            agent_ids=request.agent_ids,
            priority=request.priority,
        )

        # 构建响应
        response = CollaborateResponse(
            task=request.task,
            mode=request.mode,
            agents_involved=result.get("agents_involved", request.agent_ids or []),
            final_result=result.get("final_output")
            or result.get("consensus")
            or result.get("best_solution", {}).get("analysis", ""),
            quality_score=result.get("quality_score"),
            completion_time=result.get("completion_time", 0.0),
            status=result.get("status", "completed"),
            metadata={
                "results": result.get("results", []),
                "debate_history": result.get("debate_history"),
                "votes": result.get("votes"),
                "subtasks": result.get("subtasks"),
            },
        )

        logger.info(
            f"Multi-agent collaboration completed: tenant={tenant_id}, "
            f"mode={request.mode}, quality={result.get('quality_score', 0):.2f}"
        )

        return response

    except Exception as e:
        logger.error(f"Multi-agent collaboration failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/agents/register", response_model=RegisterAgentResponse)
async def register_agent(
    request: RegisterAgentRequest,
    tenant_id: str = Depends(get_tenant_id),
    token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> RegisterAgentResponse:
    """注册新的Agent"""
    try:
        if not hasattr(agent_engine, "multi_agent_coordinator"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Multi-agent coordinator not initialized",
            )

        from app.core.multi_agent.coordinator import Agent, AgentRole

        # 验证角色
        try:
            role = AgentRole(request.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {request.role}. Must be one of: coordinator, researcher, planner, executor, reviewer",
            )

        coordinator = agent_engine.multi_agent_coordinator

        # 创建Agent
        agent = Agent(
            agent_id=request.agent_id,
            role=role,
            llm_client=agent_engine.llm_client if hasattr(agent_engine, "llm_client") else None,
            tools=request.tools or [],
        )

        # 注册Agent
        await coordinator.register_agent(agent)

        logger.info(
            f"Agent registered: tenant={tenant_id}, id={request.agent_id}, role={request.role}"
        )

        return RegisterAgentResponse(
            agent_id=request.agent_id,
            role=request.role,
            message=f"Agent {request.agent_id} registered successfully",
        )

    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/agents", response_model=ListAgentsResponse)
async def list_agents(
    tenant_id: str = Depends(get_tenant_id),
    token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> ListAgentsResponse:
    """列出所有已注册的Agents"""
    try:
        if not hasattr(agent_engine, "multi_agent_coordinator"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Multi-agent coordinator not initialized",
            )

        coordinator = agent_engine.multi_agent_coordinator

        agents = [
            {
                "agent_id": agent_id,
                "role": agent.role.value,
                "tools_count": len(agent.tools),
                "processed_messages": len(agent.processed_messages),
            }
            for agent_id, agent in coordinator.agents.items()
        ]

        return ListAgentsResponse(agents=agents, count=len(agents))

    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/agents/{agent_id}")
async def unregister_agent(
    agent_id: str,
    tenant_id: str = Depends(get_tenant_id),
    token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> dict:
    """注销Agent

    Returns:
        dict: 注销Agent的响应
    """
    try:
        if not hasattr(agent_engine, "multi_agent_coordinator"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Multi-agent coordinator not initialized",
            )

        coordinator = agent_engine.multi_agent_coordinator

        await coordinator.unregister_agent(agent_id)

        logger.info(f"Agent unregistered: tenant={tenant_id}, id={agent_id}")

        return {"message": f"Agent {agent_id} unregistered successfully"}

    except Exception as e:
        logger.error(f"Failed to unregister agent: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/stats", response_model=MultiAgentStatsResponse)
async def get_multi_agent_stats(
    tenant_id: str = Depends(get_tenant_id),
    token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> MultiAgentStatsResponse:
    """获取Multi-Agent统计信息"""
    try:
        if not hasattr(agent_engine, "multi_agent_coordinator"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Multi-agent coordinator not initialized",
            )

        stats = agent_engine.multi_agent_coordinator.get_stats()

        return MultiAgentStatsResponse(
            total_tasks=stats["total_tasks"],
            completed_tasks=stats["completed_tasks"],
            failed_tasks=stats["failed_tasks"],
            success_rate=stats["success_rate"],
            avg_completion_time=stats["avg_completion_time"],
            collaboration_quality_avg=stats["collaboration_quality_avg"],
            active_agents=stats["active_agents"],
            agent_load=stats["agent_load"],
        )

    except Exception as e:
        logger.error(f"Failed to get multi-agent stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
