"""
请求模型定义
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ExecuteTaskRequest(BaseModel):
    """执行任务请求"""

    task: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="任务描述",
        examples=["计算 100 * 50 + 20 的结果"]
    )
    mode: str = Field(
        default="react",
        pattern="^(react|plan_execute|reflexion|simple)$",
        description="执行模式：react/plan_execute/reflexion/simple"
    )
    max_steps: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大步骤数"
    )
    tools: Optional[List[str]] = Field(
        default=None,
        description="可用工具列表，None 表示使用所有工具"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="会话 ID，用于记忆管理"
    )
    tenant_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="租户 ID"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="额外上下文信息"
    )

    @field_validator('tools')
    @classmethod
    def validate_tools(cls, v):
        if v is not None and len(v) > 20:
            raise ValueError("工具列表不能超过 20 个")
        return v


class ExecuteTaskStreamRequest(ExecuteTaskRequest):
    """流式执行任务请求"""
    pass


class RegisterToolRequest(BaseModel):
    """注册工具请求"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern="^[a-z][a-z0-9_]*$",
        description="工具名称（小写字母、数字、下划线）"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="工具描述"
    )
    function: str = Field(
        ...,
        description="函数路径，格式：module.path:function_name"
    )
    parameters: Dict[str, Any] = Field(
        ...,
        description="OpenAI Function JSON Schema 格式的参数定义"
    )
    init_args: List[Any] = Field(
        default_factory=list,
        description="初始化位置参数"
    )
    init_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="初始化关键字参数"
    )
    category: Optional[str] = Field(
        default="custom",
        description="工具分类"
    )

    @field_validator('function')
    @classmethod
    def validate_function_path(cls, v):
        if ':' not in v and '.' not in v:
            raise ValueError("函数路径格式错误，应为 'module:attr' 或 'module.attr'")
        return v


class AddMemoryRequest(BaseModel):
    """添加记忆请求"""

    user_id: str = Field(..., min_length=1, max_length=100)
    conversation_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=10000)
    role: str = Field(default="user", pattern="^(user|assistant|system)$")
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class RecallMemoryRequest(BaseModel):
    """回忆记忆请求"""

    user_id: str = Field(..., min_length=1, max_length=100)
    query: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(default=None)
    top_k: int = Field(default=5, ge=1, le=50)
    include_short_term: bool = Field(default=True)
    include_long_term: bool = Field(default=True)


class PlanTaskRequest(BaseModel):
    """规划任务请求"""

    task: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = Field(default=None)
