"""限流中间件。"""

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import Request, Response, status  # type: ignore[import]
from fastapi.responses import JSONResponse  # type: ignore[import]


class RateLimiter:
    """
    简单的内存限流器（生产环境应使用 Redis）
    """

    def __init__(self) -> None:
        self.requests: defaultdict[str, list[float]] = defaultdict(list)
        self.lock = asyncio.Lock()

    async def is_allowed(
        self, key: str, max_requests: int = 100, window_seconds: int = 60
    ) -> tuple[bool, int | None]:
        """
        检查是否允许请求

        Args:
            key: 限流键（如 user_id 或 IP）
            max_requests: 窗口内最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            (是否允许, 重试等待时间)
        """
        async with self.lock:
            now = time.time()
            cutoff = now - window_seconds

            # 清理过期记录
            self.requests[key] = [req_time for req_time in self.requests[key] if req_time > cutoff]

            # 检查是否超限
            if len(self.requests[key]) >= max_requests:
                # 计算最早请求过期的时间
                oldest = self.requests[key][0]
                retry_after = int(oldest + window_seconds - now) + 1
                return False, retry_after

            # 记录本次请求
            self.requests[key].append(now)
            return True, None


# 全局限流器实例
rate_limiter = RateLimiter()


class RateLimitMiddleware:
    """
    限流中间件

    基于租户 ID 或 IP 地址进行限流
    """

    def __init__(
        self, max_requests: int = 100, window_seconds: int = 60, key_func: Callable | None = None
    ) -> None:
        """
        初始化限流中间件

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
            key_func: 自定义限流键函数
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key_func

    def _default_key_func(self, request: Request) -> str:
        """默认限流键：优先使用租户 ID，否则使用 IP"""
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return f"tenant:{tenant_id}"

        # 获取真实 IP（考虑代理）
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else request.client.host

        return f"ip:{ip}"

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理请求"""
        # 跳过健康检查和指标接口
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)

        # 获取限流键
        key = self.key_func(request)

        # 检查限流
        allowed, retry_after = await rate_limiter.is_allowed(
            key=key, max_requests=self.max_requests, window_seconds=self.window_seconds
        )

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RateLimitExceeded",
                    "message": f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Window": str(self.window_seconds),
                },
            )

        # 处理请求
        response = await call_next(request)

        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Window"] = str(self.window_seconds)

        return response


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    路由级别的限流装饰器

    Args:
        max_requests: 最大请求数
        window_seconds: 时间窗口

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        _ = (max_requests, window_seconds)  # 保留参数以便后续扩展

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # TODO: 实现路由级别的限流逻辑
            return await func(*args, **kwargs)

        return wrapper

    return decorator
