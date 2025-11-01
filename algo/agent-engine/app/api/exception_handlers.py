"""
全局异常处理器 - 集成统一错误码规范
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from fastapi import (  # type: ignore[import]
    FastAPI,  # type: ignore[import]
    Request,
    status,
)
from fastapi.exceptions import RequestValidationError  # type: ignore[import]
from fastapi.responses import JSONResponse  # type: ignore[import]
from prometheus_client import Counter

# 添加 common 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "common"))

# 导入统一错误码
from error_codes import (
    BaseAppException,
    get_error_category,
    get_http_status,
    is_retryable,
)

# 导入原有异常（向后兼容）
from app.core.exceptions import (
    AgentEngineException,
    AuthenticationError,
    AuthorizationError,
    LLMError,
    LLMTimeoutError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ServiceNotInitializedException,
    ToolNotFoundError,
)
from app.core.exceptions import (
    ValidationError as CustomValidationError,
)

logger = logging.getLogger(__name__)

# Prometheus 指标：错误计数器
error_counter = Counter(
    "agent_engine_errors_total",
    "Total number of errors by category and code",
    ["category", "code", "endpoint"],
)


def create_error_response(
    error_code: int | str,
    message: str,
    status_code: int | None = None,
    details: dict | None = None,
    request_id: str | None = None,
    retryable: bool | None = None,
) -> JSONResponse:
    """
    创建统一的错误响应（新版 - 支持统一错误码）

    Args:
        error_code: 错误代码（整数码或字符串）
        message: 错误消息
        status_code: HTTP 状态码（None 时自动推断）
        details: 详细信息字典
        request_id: 请求 ID
        retryable: 是否可重试

    Returns:
        JSONResponse
    """
    # 自动推断 HTTP 状态码
    if status_code is None and isinstance(error_code, int):
        status_code = get_http_status(error_code)
    elif status_code is None:
        status_code = 500

    # 自动判断是否可重试
    if retryable is None and isinstance(error_code, int):
        retryable = is_retryable(error_code)

    # 构建响应内容
    content = {
        "code": error_code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
        "retryable": retryable,
    }

    if details:
        content["details"] = details

    if request_id:
        content["request_id"] = request_id

    # 添加错误分类（用于监控）
    if isinstance(error_code, int):
        content["category"] = get_error_category(error_code)

    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"X-Error-Code": str(error_code)} if error_code else {},
    )


async def agent_engine_exception_handler(
    request: Request, exc: AgentEngineException
) -> JSONResponse:
    """处理 Agent Engine 自定义异常"""
    request_id = request.headers.get("X-Request-ID")

    logger.error(
        f"Agent Engine Exception: {exc.error_code} - {exc.message}",
        extra={"error_code": exc.error_code, "request_id": request_id, "path": request.url.path},
    )

    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
    )


async def service_not_initialized_handler(
    request: Request, exc: ServiceNotInitializedException
) -> JSONResponse:
    """处理服务未初始化异常"""
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        request_id=request.headers.get("X-Request-ID"),
    )


async def validation_error_handler(request: Request, exc: CustomValidationError) -> JSONResponse:
    """处理验证错误"""
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Field: {exc.field}" if exc.field else "",
        request_id=request.headers.get("X-Request-ID"),
    )


async def pydantic_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 Pydantic 验证错误"""
    errors = exc.errors()
    error_messages = []

    for error in errors:
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append(f"{field}: {message}")

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="; ".join(error_messages),
        request_id=request.headers.get("X-Request-ID"),
    )


async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    """处理认证错误"""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    """处理授权错误"""
    detail = None
    if exc.required_permission:
        detail = f"Required permission: {exc.required_permission}"

    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        request_id=request.headers.get("X-Request-ID"),
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """处理限流错误"""
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "retry_after": exc.retry_after,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request.headers.get("X-Request-ID"),
        },
        headers=headers,
    )


async def tool_not_found_handler(request: Request, exc: ToolNotFoundError) -> JSONResponse:
    """处理工具未找到错误"""
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Tool name: {exc.tool_name}",
        request_id=request.headers.get("X-Request-ID"),
    )


async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    """处理资源未找到错误"""
    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Resource type: {exc.resource_type}, ID: {exc.resource_id}",
        request_id=request.headers.get("X-Request-ID"),
    )


async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    """处理 LLM 服务错误"""
    logger.error(
        f"LLM Error: {exc.message}",
        extra={"provider": exc.provider, "request_id": request.headers.get("X-Request-ID")},
    )

    return create_error_response(
        error_code=exc.error_code,
        message="LLM service temporarily unavailable",
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=exc.message if exc.provider else None,  # type: ignore
        request_id=request.headers.get("X-Request-ID"),  # type: ignore
    )


async def llm_timeout_handler(request: Request, exc: LLMTimeoutError) -> JSONResponse:
    """处理 LLM 超时错误"""
    return create_error_response(
        error_code=exc.error_code,
        message="LLM request timeout",
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        detail=f"Provider: {exc.provider}" if exc.provider else "",
        request_id=request.headers.get("X-Request-ID"),
    )


async def unified_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """
    统一错误码异常处理器（新版）

    处理所有使用统一错误码的异常
    """
    request_id = request.headers.get("X-Request-ID")
    endpoint = request.url.path

    # 记录错误日志
    logger.error(
        f"[{exc.code}] {exc.message}",
        extra={
            "error_code": exc.code,
            "category": get_error_category(exc.code),
            "request_id": request_id,
            "endpoint": endpoint,
            "details": exc.details,
        },
        exc_info=exc.cause is not None,
    )

    # 更新 Prometheus 指标
    error_counter.labels(
        category=get_error_category(exc.code), code=exc.code, endpoint=endpoint
    ).inc()

    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的异常"""
    request_id = request.headers.get("X-Request-ID")
    endpoint = request.url.path

    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"request_id": request_id, "path": endpoint, "method": request.method},
    )

    # 更新 Prometheus 指标
    error_counter.labels(
        category="SYSTEM",
        code=50001,  # UNKNOWN_ERROR
        endpoint=endpoint,
    ).inc()

    return create_error_response(
        error_code=50001,  # UNKNOWN_ERROR
        message="An unexpected error occurred",
        details={"error": str(exc)} if logger.level == logging.DEBUG else None,
        request_id=request_id,
    )


def register_exception_handlers(app: FastAPI) -> None:  # type: ignore[import]
    """
    注册所有异常处理器

    Args:
        app: FastAPI 应用实例
    """
    # 统一错误码异常（最高优先级）
    app.add_exception_handler(BaseAppException, unified_exception_handler)

    # Pydantic 验证错误
    app.add_exception_handler(RequestValidationError, pydantic_validation_error_handler)

    # 自定义异常（向后兼容）
    app.add_exception_handler(ServiceNotInitializedException, service_not_initialized_handler)
    app.add_exception_handler(CustomValidationError, validation_error_handler)
    app.add_exception_handler(AuthenticationError, authentication_error_handler)
    app.add_exception_handler(AuthorizationError, authorization_error_handler)
    app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)
    app.add_exception_handler(ToolNotFoundError, tool_not_found_handler)
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
    app.add_exception_handler(LLMTimeoutError, llm_timeout_handler)
    app.add_exception_handler(LLMError, llm_error_handler)

    # 通用 Agent Engine 异常
    app.add_exception_handler(AgentEngineException, agent_engine_exception_handler)

    # 捕获所有未处理的异常
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered (with unified error codes)")
