"""限流中间件 - Redis 滑动窗口限流"""

import logging
import time
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """限流中间件 - 基于 Redis 的滑动窗口限流"""

    def __init__(
        self,
        app,
        redis_client=None,
        max_requests: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.enabled = enabled
        self._memory_cache = {}  # 备用内存缓存

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled:
            return await call_next(request)

        # 跳过健康检查和指标端点
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)

        # 获取客户端标识
        client_id = self._get_client_id(request)

        # 检查限流
        allowed = await self._check_rate_limit(client_id)

        if not allowed:
            trace_id = getattr(request.state, "trace_id", "unknown")
            logger.warning(
                f"Rate limit exceeded",
                extra={
                    "trace_id": trace_id,
                    "client_id": client_id,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds} seconds.",
            )

        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用租户ID（如果有）
        tenant_id = request.headers.get("X-Tenant-Id")
        if tenant_id:
            return f"tenant:{tenant_id}"

        # 使用客户端 IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def _check_rate_limit(self, client_id: str) -> bool:
        """检查是否超过限流"""
        current_time = time.time()
        key = f"rate_limit:{client_id}"

        # 使用 Redis（如果可用）
        if self.redis_client:
            try:
                return await self._check_rate_limit_redis(key, current_time)
            except Exception as e:
                logger.error(f"Redis rate limit check failed: {e}, falling back to memory")

        # 备用：使用内存缓存
        return self._check_rate_limit_memory(key, current_time)

    async def _check_rate_limit_redis(self, key: str, current_time: float) -> bool:
        """使用 Redis 检查限流（滑动窗口）"""
        # 滑动窗口起始时间
        window_start = current_time - self.window_seconds

        # 使用 Redis 的 sorted set 实现滑动窗口
        # 1. 移除窗口外的记录
        await self.redis_client.zremrangebyscore(key, 0, window_start)

        # 2. 获取当前窗口内的请求数
        count = await self.redis_client.zcard(key)

        if count >= self.max_requests:
            return False

        # 3. 添加当前请求
        await self.redis_client.zadd(key, {str(current_time): current_time})

        # 4. 设置过期时间
        await self.redis_client.expire(key, self.window_seconds + 10)

        return True

    def _check_rate_limit_memory(self, key: str, current_time: float) -> bool:
        """使用内存检查限流（简化版滑动窗口）"""
        window_start = current_time - self.window_seconds

        # 获取或创建时间戳列表
        if key not in self._memory_cache:
            self._memory_cache[key] = []

        timestamps = self._memory_cache[key]

        # 移除窗口外的记录
        timestamps[:] = [ts for ts in timestamps if ts > window_start]

        if len(timestamps) >= self.max_requests:
            return False

        # 添加当前请求
        timestamps.append(current_time)

        return True
