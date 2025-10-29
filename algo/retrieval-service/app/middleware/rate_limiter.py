"""
Rate Limiting Middleware - 速率限制中间件
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis
from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件 - 使用Redis实现滑动窗口限流

    支持:
    - 基于IP或API Key的限流
    - 滑动窗口算法
    - 可配置速率和窗口大小
    """

    def __init__(
        self,
        app: Any,
        redis_client: redis.Redis | None = None,
        rate_limit: int = 100,  # 每个窗口的最大请求数
        window_size: int = 60,  # 窗口大小（秒）
        whitelist_paths: set | None = None,
    ) -> None:
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limit = rate_limit
        self.window_size = window_size
        self.whitelist_paths = whitelist_paths or {
            "/health",
            "/ready",
            "/metrics",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 白名单路径跳过限流
        if request.url.path in self.whitelist_paths:
            return await call_next(request)

        # 如果没有Redis客户端，跳过限流
        if not self.redis_client:
            logger.warning("Rate limiter: Redis client not available, skipping rate limit")
            return await call_next(request)

        # 获取限流键（优先使用API key，否则使用IP）
        rate_limit_key = self._get_rate_limit_key(request)

        # 检查速率限制
        allowed, remaining, reset_time = await self._check_rate_limit(rate_limit_key)

        # 添加速率限制信息到响应头
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {int(reset_time - time.time())} seconds",
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time - time.time())),
                },
            )

        # 处理请求
        response = await call_next(request)

        # 添加速率限制信息到响应头
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        return response

    def _get_rate_limit_key(self, request: Request) -> str:
        """生成速率限制键"""
        # 优先使用API key
        if hasattr(request.state, "api_key"):
            identifier = request.state.api_key
        else:
            # 使用客户端IP
            identifier = request.client.host if request.client else "unknown"

        return f"rate_limit:{identifier}"

    async def _check_rate_limit(self, key: str) -> tuple[bool, int, float]:
        """
        检查速率限制（滑动窗口算法）

        Returns:
            (是否允许, 剩余配额, 重置时间戳)
        """
        try:
            now = time.time()
            window_start = now - self.window_size

            # 使用 Redis Sorted Set 实现滑动窗口
            if not self.redis_client:
                return True, self.rate_limit, time.time() + self.window_size

            pipe = self.redis_client.pipeline()

            # 删除窗口外的旧记录
            pipe.zremrangebyscore(key, 0, window_start)

            # 统计当前窗口内的请求数
            pipe.zcard(key)

            # 添加当前请求
            pipe.zadd(key, {str(now): now})

            # 设置过期时间
            pipe.expire(key, self.window_size)

            results = await pipe.execute()
            current_count = results[1]

            # 检查是否超过限制
            if current_count >= self.rate_limit:
                # 获取窗口内最早的请求时间
                if not self.redis_client:
                    return False, 0, now + self.window_size

                oldest = await self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = oldest[0][1] + self.window_size if oldest else now + self.window_size

                return False, 0, reset_time

            remaining = self.rate_limit - current_count - 1
            reset_time = now + self.window_size

            return True, remaining, reset_time

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # 失败时允许请求通过
            return True, self.rate_limit, time.time() + self.window_size
