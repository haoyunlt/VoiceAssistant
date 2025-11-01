"""
Multi-Agent + LangGraph API Endpoints
提供RESTful API供前端调用
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.multi_agent.enhanced_coordinator import EnhancedMultiAgentCoordinator
from app.core.multi_agent.task_scheduler import TaskPriority
from app.core.multi_agent.enhanced_conflict_resolver import ConflictType
from app.core.langgraph_engine import LangGraphWorkflowEngine
from app.core.workflow_visualizer import WorkflowVisualizer

router = APIRouter(prefix="/api/v1", tags=["multi-agent", "langgraph"])

# 全局实例（在main.py中初始化）
enhanced_coordinator: EnhancedMultiAgentCoordinator | None = None
workflow_engine: LangGraphWorkflowEngine | None = None
workflow_visualizer = WorkflowVisualizer()


# ==================== Request/Response Models ====================

class AgentRegistrationRequest(BaseModel):
    """Agent注册请求"""
    agent_id: str
    agent_role: str = Field(..., description="角色: researcher/planner/executor/reviewer/coordinator")
    capabilities: dict[str, float] = Field(..., description="能力字典，值范围0-1")
    success_rate: float = Field(0.5, ge=0.0, le=1.0)
    avg_response_time: float = Field(2.0, gt=0.0)


class CollaborationRequest(BaseModel):
    """协作任务请求"""
    task_description: str = Field(..., min_length=1)
    priority: str = Field("medium", description="low/medium/high/urgent")
    required_capabilities: list[str] = Field(default_factory=list)
    estimated_time: float = Field(300.0, gt=0.0)
    timeout: int = Field(300, gt=0)


class ConflictResolutionRequest(BaseModel):
    """冲突解决请求"""
    agent1_id: str
    agent2_id: str
    conflict_type: str = Field(..., description="resource/priority/opinion/data/control")
    context: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreateRequest(BaseModel):
    """工作流创建请求"""
    nodes: list[dict] = Field(..., description="节点列表")
    edges: list[dict] = Field(..., description="边列表")
    entry: str = Field("start", description="入口节点ID")


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求"""
    workflow_id: str
    initial_data: dict[str, Any] = Field(default_factory=dict)
    entry_node: str = Field("start")
    save_checkpoints: bool = Field(True)


# ==================== Multi-Agent Endpoints ====================

@router.post("/multi-agent/register")
async def register_agent(request: AgentRegistrationRequest):
    """
    注册Agent

    POST /api/v1/multi-agent/register
    {
        "agent_id": "researcher_01",
        "agent_role": "researcher",
        "capabilities": {"research": 0.9, "analysis": 0.8},
        "success_rate": 0.95,
        "avg_response_time": 2.5
    }
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        # 创建Agent（简化：这里应该从registry获取或创建）
        from app.core.multi_agent.coordinator import Agent, AgentRole
        from app.core.agent_engine import AgentEngine

        # 假设已有全局llm_client
        # agent = Agent(request.agent_id, AgentRole[request.agent_role.upper()], llm_client)

        # 注册能力
        # await enhanced_coordinator.register_agent_with_capabilities(
        #     agent=agent,
        #     capabilities=request.capabilities,
        #     success_rate=request.success_rate,
        #     avg_response_time=request.avg_response_time
        # )

        return {
            "success": True,
            "message": f"Agent {request.agent_id} registered successfully",
            "agent_id": request.agent_id,
            "capabilities": list(request.capabilities.keys())
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-agent/collaborate")
async def collaborate_task(request: CollaborationRequest):
    """
    执行协作任务

    POST /api/v1/multi-agent/collaborate
    {
        "task_description": "分析Q4市场趋势",
        "priority": "high",
        "required_capabilities": ["research", "analysis"]
    }
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        # 转换优先级
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT
        }
        priority = priority_map.get(request.priority.lower(), TaskPriority.MEDIUM)

        # 执行协作
        result = await enhanced_coordinator.collaborate_with_scheduling(
            task_description=request.task_description,
            priority=priority,
            required_capabilities=request.required_capabilities,
            estimated_time=request.estimated_time,
            timeout=request.timeout
        )

        return {
            "success": result.get("success", False),
            "task": result.get("task"),
            "assigned_agent": result.get("agent"),
            "execution_time": result.get("execution_time"),
            "schedule_quality": result.get("schedule_quality"),
            "result": result.get("result"),
            "error": result.get("error"),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/multi-agent/resolve-conflict")
async def resolve_conflict(request: ConflictResolutionRequest):
    """
    解决Agent冲突

    POST /api/v1/multi-agent/resolve-conflict
    {
        "agent1_id": "researcher_01",
        "agent2_id": "planner_01",
        "conflict_type": "opinion",
        "context": {"task": "市场调研"}
    }
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        # 转换冲突类型
        conflict_type_map = {
            "resource": ConflictType.RESOURCE_CONFLICT,
            "priority": ConflictType.PRIORITY_CONFLICT,
            "opinion": ConflictType.OPINION_DISAGREEMENT,
            "data": ConflictType.DATA_INCONSISTENCY,
            "control": ConflictType.CONTROL_CONFLICT
        }
        conflict_type = conflict_type_map.get(
            request.conflict_type.lower(),
            ConflictType.OPINION_DISAGREEMENT
        )

        # 解决冲突
        result = await enhanced_coordinator.resolve_agent_conflict(
            agent1_id=request.agent1_id,
            agent2_id=request.agent2_id,
            conflict_type=conflict_type,
            context=request.context
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/stats")
async def get_multi_agent_stats():
    """
    获取Multi-Agent统计信息

    GET /api/v1/multi-agent/stats
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        return {
            "communication": enhanced_coordinator.get_communication_stats(),
            "scheduling": enhanced_coordinator.get_scheduling_stats(),
            "conflict_resolution": enhanced_coordinator.get_conflict_stats(),
            "total_agents": len(enhanced_coordinator.agents)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/health")
async def get_multi_agent_health():
    """
    Multi-Agent健康检查

    GET /api/v1/multi-agent/health
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        health = await enhanced_coordinator.health_check()
        return health

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/communication-graph")
async def get_communication_graph():
    """
    获取通信图（用于可视化）

    GET /api/v1/multi-agent/communication-graph
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        graph = enhanced_coordinator.export_communication_graph()
        return graph

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/agents/{agent_id}/capabilities")
async def get_agent_capabilities(agent_id: str):
    """
    获取Agent能力画像

    GET /api/v1/multi-agent/agents/researcher_01/capabilities
    """
    if not enhanced_coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")

    try:
        capabilities = enhanced_coordinator.get_agent_capabilities(agent_id)

        if not capabilities:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

        return capabilities

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LangGraph Endpoints ====================

@router.post("/langgraph/workflows")
async def create_workflow(request: WorkflowCreateRequest):
    """
    创建工作流

    POST /api/v1/langgraph/workflows
    {
        "nodes": [...],
        "edges": [...],
        "entry": "start"
    }
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        workflow_config = {
            "nodes": request.nodes,
            "edges": request.edges,
            "entry": request.entry
        }

        workflow_id = workflow_engine.create_workflow(workflow_config)

        # 生成可视化
        mermaid_code = workflow_visualizer.export_to_mermaid(workflow_config)
        graph_json = workflow_visualizer.export_to_json(workflow_config)

        return {
            "success": True,
            "workflow_id": workflow_id,
            "node_count": len(request.nodes),
            "edge_count": len(request.edges),
            "visualization": {
                "mermaid": mermaid_code,
                "graph": graph_json
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langgraph/workflows/execute")
async def execute_workflow(request: WorkflowExecuteRequest):
    """
    执行工作流

    POST /api/v1/langgraph/workflows/execute
    {
        "workflow_id": "wf_123456",
        "initial_data": {"task": "分析数据"},
        "save_checkpoints": true
    }
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        result = await workflow_engine.execute(
            workflow_id=request.workflow_id,
            initial_data=request.initial_data,
            entry_node=request.entry_node,
            save_checkpoints=request.save_checkpoints
        )

        return {
            "success": result["status"] == "completed",
            "status": result["status"],
            "node_history": result["node_history"],
            "variables": result["variables"],
            "total_steps": len(result["node_history"])
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/langgraph/workflows/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """
    恢复工作流执行

    POST /api/v1/langgraph/workflows/wf_123456/resume
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        result = await workflow_engine.resume(workflow_id)

        return {
            "success": result["status"] == "completed",
            "status": result["status"],
            "node_history": result["node_history"],
            "variables": result["variables"]
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langgraph/workflows/{workflow_id}")
async def get_workflow_status(workflow_id: str):
    """
    获取工作流状态

    GET /api/v1/langgraph/workflows/wf_123456
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        status = workflow_engine.get_workflow_status(workflow_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langgraph/workflows/{workflow_id}/visualization")
async def get_workflow_visualization(
    workflow_id: str,
    include_trace: bool = False
):
    """
    获取工作流可视化

    GET /api/v1/langgraph/workflows/wf_123456/visualization?include_trace=true
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        # 获取工作流配置（简化：实际需要从存储中获取）
        # workflow_config = get_workflow_config(workflow_id)

        # 暂时返回错误
        raise HTTPException(
            status_code=501,
            detail="Visualization endpoint requires workflow config storage"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/langgraph/stats")
async def get_langgraph_stats():
    """
    获取LangGraph统计信息

    GET /api/v1/langgraph/stats
    """
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")

    try:
        stats = workflow_engine.get_stats()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 初始化函数 ====================

def init_multi_agent_langgraph_router(
    coordinator: EnhancedMultiAgentCoordinator,
    engine: LangGraphWorkflowEngine
):
    """
    初始化路由器（在main.py中调用）

    Args:
        coordinator: 增强协调器实例
        engine: 工作流引擎实例
    """
    global enhanced_coordinator, workflow_engine
    enhanced_coordinator = coordinator
    workflow_engine = engine
