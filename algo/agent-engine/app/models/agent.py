"""Agent相关数据模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field  # type: ignore[import]


class AgentStatus(str, Enum):
    """Agent状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class StepType(str, Enum):
    """步骤类型"""

    THOUGHT = "thought"  # 思考
    ACTION = "action"  # 行动
    OBSERVATION = "observation"  # 观察
    ANSWER = "answer"  # 回答


class AgentStep(BaseModel):
    """Agent执行步骤"""

    step_number: int
    step_type: StepType
    content: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: Any | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """Agent任务"""

    task_id: str | None = None
    task: str = Field(..., description="任务描述")
    context: dict[str, Any] = Field(default_factory=dict, description="上下文")
    tools: list[str] = Field(default_factory=list, description="可用工具")
    max_iterations: int = Field(default=10, description="最大迭代次数")
    model: str | None = None
    temperature: float = Field(default=0.7)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResult(BaseModel):
    """Agent执行结果"""

    task_id: str
    result: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    status: AgentStatus
    iterations: int = 0
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error: str | None = None


class ToolDefinition(BaseModel):
    """工具定义"""

    name: str
    description: str
    parameters: dict[str, Any]
    required_params: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    category: str = "general"
