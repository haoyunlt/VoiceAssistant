"""
响应模型定义
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态")
    service: str = Field(..., description="服务名称")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ReadinessCheck(BaseModel):
    """就绪检查项"""

    engine: bool
    llm: bool
    tools: bool
    memory: bool


class ReadinessResponse(BaseModel):
    """就绪检查响应"""

    ready: bool = Field(..., description="是否就绪")
    checks: ReadinessCheck = Field(..., description="各组件检查状态")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ConfigInfoResponse(BaseModel):
    """配置信息响应"""

    mode: str
    service: str
    nacos_enabled: bool
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExecuteTaskResponse(BaseModel):
    """执行任务响应"""

    task: str = Field(..., description="任务描述")
    mode: str = Field(..., description="执行模式")
    result: str | None = Field(None, description="执行结果")
    final_answer: str | None = Field(None, description="最终答案")
    step_count: int = Field(default=0, description="执行步骤数")
    tool_call_count: int = Field(default=0, description="工具调用次数")
    execution_time: float = Field(..., description="执行时间（秒）")
    conversation_id: str | None = Field(None, description="会话 ID")
    steps: list[dict[str, Any]] | None = Field(None, description="执行步骤详情")
    metadata: dict[str, Any] | None = Field(None, description="元数据")


class ToolDefinition(BaseModel):
    """工具定义"""

    name: str
    description: str
    parameters: dict[str, Any]
    category: str | None = None


class ListToolsResponse(BaseModel):
    """工具列表响应"""

    tools: list[ToolDefinition]
    count: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class RegisterToolResponse(BaseModel):
    """注册工具响应"""

    status: str = Field(..., description="注册状态")
    tool: ToolDefinition = Field(..., description="工具定义")
    total: int = Field(..., description="工具总数")
    message: str = Field(default="Tool registered successfully")


class UnregisterToolResponse(BaseModel):
    """注销工具响应"""

    message: str
    tool_name: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MemoryResponse(BaseModel):
    """记忆响应"""

    conversation_id: str
    memory: Any
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ClearMemoryResponse(BaseModel):
    """清除记忆响应"""

    conversation_id: str
    status: str
    message: str = Field(default="Memory cleared successfully")


class StatsResponse(BaseModel):
    """统计信息响应"""

    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    total_steps: int
    total_tool_calls: int
    avg_execution_time: float
    success_rate: float
    avg_steps_per_task: float
    avg_tool_calls_per_task: float
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    detail: str | None = Field(None, description="详细信息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request_id: str | None = Field(None, description="请求 ID")
