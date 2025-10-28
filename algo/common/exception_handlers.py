"""
统一的 FastAPI 异常处理器

基于 common/exceptions.py 中定义的异常体系，为所有服务提供一致的错误响应格式。
"""

import logging
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    ValidationError,
    VoiceHelperError,
    get_http_status_code,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理器到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
    """

    @app.exception_handler(VoiceHelperError)
    async def voice_assistant_exception_handler(request: Request, exc: VoiceHelperError):
        """处理自定义业务异常"""
        status_code = get_http_status_code(exc)

        # 记录日志
        log_level = logging.ERROR if status_code >= 500 else logging.WARNING
        logger.log(
            log_level,
            f"Business exception: {exc}",
            extra={
                "error_code": exc.code,
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "request_id": request.headers.get("X-Request-ID", ""),
            },
            exc_info=exc.cause if log_level == logging.ERROR else None,
        )

        # 构造响应
        response_data = exc.to_dict()

        # 添加请求追踪ID
        headers = {}
        if request_id := request.headers.get("X-Request-ID"):
            headers["X-Request-ID"] = request_id
            response_data["request_id"] = request_id

        # 添加错误代码头部（便于客户端识别）
        headers["X-Error-Code"] = exc.code

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误（Pydantic）"""
        logger.warning(
            f"Validation error: {exc}",
            extra={
                "path": request.url.path,
                "errors": exc.errors(),
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "Invalid request data",
                "details": exc.errors(),
                "request_id": request.headers.get("X-Request-ID", ""),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 HTTP 异常"""
        logger.warning(
            f"HTTP exception: {exc.status_code} - {exc.detail}",
            extra={
                "path": request.url.path,
                "status_code": exc.status_code,
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": exc.detail,
                "request_id": request.headers.get("X-Request-ID", ""),
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """处理未捕获的异常"""
        logger.exception(
            f"Unhandled exception: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
        )

        # 从追踪中获取 trace_id（如果有）
        try:
            from .telemetry import get_current_span

            span = get_current_span()
            trace_id = span.get_span_context().trace_id if span.is_recording() else None
        except Exception:
            trace_id = None

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred. Please contact support if the problem persists.",
                "request_id": request.headers.get("X-Request-ID", ""),
                "trace_id": str(trace_id) if trace_id else None,
                "path": request.url.path,
            },
        )

    logger.info("Exception handlers registered")


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Union[dict, None] = None,
) -> JSONResponse:
    """
    创建标准错误响应

    Args:
        error_code: 错误代码
        message: 错误消息
        status_code: HTTP 状态码
        details: 额外详情

    Returns:
        JSONResponse 对象
    """
    content = {
        "error": error_code,
        "message": message,
    }

    if details:
        content["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content,
    )
