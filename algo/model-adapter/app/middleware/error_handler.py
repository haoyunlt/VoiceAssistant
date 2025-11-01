"""错误处理中间件."""

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """全局错误处理中间件."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求."""
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "unknown")

        try:
            response = await call_next(request)
            return response

        except Exception as exc:
            # 记录错误
            logger.error(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(exc),
                    "duration_ms": int((time.time() - start_time) * 1000),
                },
                exc_info=True,
            )

            # 返回统一错误响应
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                },
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """记录请求和响应."""
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "unknown")

        # 记录请求
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown",
            },
        )

        # 处理请求
        response = await call_next(request)

        # 记录响应
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(duration_ms)

        return response
