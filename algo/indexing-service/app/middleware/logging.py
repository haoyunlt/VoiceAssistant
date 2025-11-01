"""结构化日志中间件"""

import json
import logging
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    结构化日志中间件

    记录每个请求的详细信息（JSON格式）
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        start_time = time.time()

        # 获取请求信息
        request_id = getattr(request.state, "request_id", "unknown")
        tenant_id = getattr(request.state, "tenant_id", "default")

        # 记录请求日志
        request_log = {
            "event": "request_started",
            "request_id": request_id,
            "tenant_id": tenant_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent"),
        }
        logger.info(json.dumps(request_log))

        # 处理请求
        try:
            response = await call_next(request)

            # 记录响应日志
            duration = time.time() - start_time
            response_log = {
                "event": "request_completed",
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "duration": round(duration, 3),
            }
            logger.info(json.dumps(response_log))

            return response

        except Exception as e:
            # 记录错误日志
            duration = time.time() - start_time
            error_log = {
                "event": "request_failed",
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "url": str(request.url),
                "error": str(e),
                "error_type": type(e).__name__,
                "duration": round(duration, 3),
            }
            logger.error(json.dumps(error_log))
            raise
