"""
统一响应格式 - Python版本

与Go服务保持一致的响应格式，便于前端统一处理
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UnifiedErrorResponse(BaseModel):
    """统一错误响应格式"""

    success: bool = Field(default=False, description="是否成功")
    error_code: str = Field(..., description="错误码（5位）")
    message: str = Field(..., description="错误消息（用户可读）")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # 可选字段
    request_id: Optional[str] = Field(None, description="请求ID")
    trace_id: Optional[str] = Field(None, description="链路追踪ID")
    path: Optional[str] = Field(None, description="请求路径")
    method: Optional[str] = Field(None, description="请求方法")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")
    stack: Optional[str] = Field(None, description="堆栈信息（仅debug）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error_code": "20001",
                "message": "LLM调用失败",
                "timestamp": "2025-11-01T10:30:00Z",
                "request_id": "req-123456",
                "trace_id": "trace-abc",
            }
        }


class UnifiedSuccessResponse(BaseModel):
    """统一成功响应格式"""

    success: bool = Field(default=True, description="是否成功")
    data: Optional[Any] = Field(None, description="响应数据")
    message: Optional[str] = Field(None, description="可选消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    request_id: Optional[str] = Field(None, description="请求ID")
    meta: Optional[Dict[str, Any]] = Field(None, description="元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"result": "success"},
                "timestamp": "2025-11-01T10:30:00Z",
                "request_id": "req-123456",
            }
        }


# 错误码与HTTP状态码映射
ERROR_CODE_MAPPING: Dict[str, int] = {
    # 1xxxx - 通用错误
    "10000": 400,  # 请求参数错误
    "10001": 401,  # 未授权
    "10002": 403,  # 无权限
    "10003": 404,  # 资源不存在
    "10004": 408,  # 请求超时
    "10005": 429,  # 请求过多
    "10006": 500,  # 内部错误
    # 2xxxx - 业务错误
    "20001": 400,  # LLM调用失败
    "20002": 503,  # LLM超时
    "20003": 429,  # LLM限流
    "20004": 400,  # Agent执行失败
    "20005": 400,  # RAG检索失败
    # 3xxxx - 数据错误
    "30001": 400,  # 数据验证失败
    "30002": 404,  # 数据不存在
    "30003": 409,  # 数据冲突
    "30004": 408,  # 查询超时
    # 4xxxx - 服务错误
    "40001": 503,  # 服务不可用
    "40002": 504,  # 服务超时
    "40003": 503,  # 熔断器打开
    # 5xxxx - 系统错误
    "50001": 500,  # 系统错误
    "50002": 500,  # 数据库错误
    "50003": 500,  # 缓存错误
    "50004": 500,  # 消息队列错误
}

# 可重试错误码
RETRYABLE_ERROR_CODES = {
    "10004",  # 请求超时
    "10005",  # 请求过多
    "20002",  # LLM超时
    "20003",  # LLM限流
    "30004",  # 查询超时
    "40001",  # 服务不可用
    "40002",  # 服务超时
    "40003",  # 熔断器打开
}


class CommonErrors:
    """常见错误码定义"""

    # 通用错误
    BAD_REQUEST = "10000"
    UNAUTHORIZED = "10001"
    FORBIDDEN = "10002"
    NOT_FOUND = "10003"
    TIMEOUT = "10004"
    TOO_MANY_REQUESTS = "10005"
    INTERNAL_SERVER_ERROR = "10006"

    # 业务错误
    LLM_FAILED = "20001"
    LLM_TIMEOUT = "20002"
    LLM_RATE_LIMITED = "20003"
    AGENT_FAILED = "20004"
    RAG_FAILED = "20005"

    # 数据错误
    DATA_VALIDATION = "30001"
    DATA_NOT_FOUND = "30002"
    DATA_CONFLICT = "30003"
    QUERY_TIMEOUT = "30004"

    # 服务错误
    SERVICE_UNAVAILABLE = "40001"
    SERVICE_TIMEOUT = "40002"
    CIRCUIT_BREAKER_OPEN = "40003"

    # 系统错误
    SYSTEM_ERROR = "50001"
    DATABASE_ERROR = "50002"
    CACHE_ERROR = "50003"
    MQ_ERROR = "50004"


def create_error_response(
    error_code: str,
    message: str,
    request_id: str | None = None,
    trace_id: str | None = None,
    path: str | None = None,
    method: str | None = None,
    details: Dict[str, Any] | None = None,
    stack: str | None = None,
) -> UnifiedErrorResponse:
    """
    创建错误响应

    Args:
        error_code: 错误码
        message: 错误消息
        request_id: 请求ID
        trace_id: 链路追踪ID
        path: 请求路径
        method: 请求方法
        details: 详细信息
        stack: 堆栈信息

    Returns:
        统一错误响应
    """
    return UnifiedErrorResponse(
        error_code=error_code,
        message=message,
        request_id=request_id,
        trace_id=trace_id,
        path=path,
        method=method,
        details=details,
        stack=stack,
    )


def create_success_response(
    data: Any = None,
    message: str | None = None,
    request_id: str | None = None,
    meta: Dict[str, Any] | None = None,
) -> UnifiedSuccessResponse:
    """
    创建成功响应

    Args:
        data: 响应数据
        message: 可选消息
        request_id: 请求ID
        meta: 元数据

    Returns:
        统一成功响应
    """
    return UnifiedSuccessResponse(
        data=data,
        message=message,
        request_id=request_id,
        meta=meta,
    )


def get_http_status(error_code: str) -> int:
    """
    获取错误码对应的HTTP状态码

    Args:
        error_code: 错误码

    Returns:
        HTTP状态码
    """
    return ERROR_CODE_MAPPING.get(error_code, 500)


def is_retryable(error_code: str) -> bool:
    """
    判断错误是否可重试

    Args:
        error_code: 错误码

    Returns:
        是否可重试
    """
    return error_code in RETRYABLE_ERROR_CODES


# FastAPI集成示例
"""
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def unified_exception_handler(request: Request, exc: Exception):
    '''统一异常处理器'''
    
    # 从请求中获取信息
    request_id = request.headers.get("X-Request-ID")
    trace_id = request.headers.get("X-Trace-ID")
    
    # 创建错误响应
    error_response = create_error_response(
        error_code=CommonErrors.INTERNAL_SERVER_ERROR,
        message=str(exc),
        request_id=request_id,
        trace_id=trace_id,
        path=str(request.url.path),
        method=request.method,
    )
    
    status_code = get_http_status(error_response.error_code)
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(exclude_none=True),
    )
"""

