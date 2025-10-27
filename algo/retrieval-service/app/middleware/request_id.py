"""
Request ID Middleware - 为每个请求添加唯一ID用于追踪
"""

import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID中间件 - 为每个请求生成唯一ID"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 从请求头获取或生成新的请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 将请求ID存储在请求状态中，供日志使用
        request.state.request_id = request_id

        # 处理请求
        response = await call_next(request)

        # 添加请求ID到响应头
        response.headers["X-Request-ID"] = request_id

        return response
