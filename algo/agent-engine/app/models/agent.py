"""Agent相关数据模型"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    """Agent状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class StepType(str, Enum):
    """步骤类型"""
    THOUGHT = "thought"          # 思考
    ACTION = "action"            # 行动
    OBSERVATION = "observation"  # 观察
    ANSWER = "answer"            # 回答


class AgentStep(BaseModel):
    """Agent执行步骤"""
    step_number: int
    step_type: StepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """Agent任务"""
    task_id: Optional[str] = None
    task: str = Field(..., description="任务描述")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文")
    tools: List[str] = Field(default_factory=list, description="可用工具")
    max_iterations: int = Field(default=10, description="最大迭代次数")
    model: Optional[str] = None
    temperature: float = Field(default=0.7)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResult(BaseModel):
    """Agent执行结果"""
    task_id: str
    result: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    status: AgentStatus
    iterations: int = 0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str] = Field(default_factory=list)
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    category: str = "general"
