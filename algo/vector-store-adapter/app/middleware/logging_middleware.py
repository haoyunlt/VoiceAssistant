"""日志中间件 - 添加 trace_id 和请求日志"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件 - 记录请求和响应"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 生成 trace_id
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        # 记录请求开始
        start_time = time.time()

        logger.info(
            f"Request started",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            },
        )

        # 处理请求
        try:
            response = await call_next(request)

            # 记录请求完成
            duration = time.time() - start_time
            logger.info(
                f"Request completed",
                extra={
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

            # 添加 trace_id 到响应头
            response.headers["X-Trace-Id"] = trace_id

            return response

        except Exception as e:
            # 记录错误
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                },
                exc_info=True,
            )
            raise
