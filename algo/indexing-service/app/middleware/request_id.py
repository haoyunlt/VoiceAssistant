"""请求ID中间件 - 用于分布式追踪"""
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    请求ID中间件

    为每个请求生成唯一ID，用于日志关联和分布式追踪
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 生成或获取请求ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 将请求ID添加到request.state，供后续使用
        request.state.request_id = request_id
        request.state.start_time = time.time()

        # 获取租户ID
        tenant_id = request.headers.get("X-Tenant-ID") or "default"
        request.state.tenant_id = tenant_id

        # 处理请求
        response = await call_next(request)

        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(time.time() - request.state.start_time)

        return response
