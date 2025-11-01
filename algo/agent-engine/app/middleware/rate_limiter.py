"""限流中间件 - 基于 Redis 的生产级实现。"""

import logging
import os
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import Request, Response, status  # type: ignore[import]
from fastapi.responses import JSONResponse  # type: ignore[import]

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    基于 Redis 的限流器（滑动窗口算法）

    使用 Redis Sorted Set 实现滑动窗口限流，支持分布式部署
    """

    def __init__(self, redis_client=None) -> None:
        """
        初始化限流器

        Args:
            redis_client: Redis 客户端实例（redis.asyncio.Redis）
        """
        self.redis = redis_client
        self._warned_no_redis = False

    async def is_allowed(
        self, key: str, max_requests: int = 100, window_seconds: int = 60
    ) -> tuple[bool, int | None]:
        """
        检查是否允许请求（滑动窗口算法）

        Args:
            key: 限流键（如 tenant:xxx 或 user:xxx）
            max_requests: 窗口内最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            (是否允许, 重试等待时间)
        """
        if not self.redis:
            # 如果 Redis 不可用，记录警告并允许请求通过
            if not self._warned_no_redis:
                logger.warning("Redis not available, rate limiting disabled")
                self._warned_no_redis = True
            return True, None

        try:
            now = time.time()
            redis_key = f"ratelimit:{key}"

            # 使用 Lua 脚本保证原子性
            lua_script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local window = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            local cutoff = now - window

            -- 清理过期记录
            redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)

            -- 获取当前窗口内的请求数
            local count = redis.call('ZCARD', key)

            if count >= max_requests then
                -- 超限，计算最早请求的时间
                local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
                if #oldest > 0 then
                    local retry_after = math.ceil(tonumber(oldest[2]) + window - now)
                    return {0, retry_after}
                end
                return {0, window}
            end

            -- 添加当前请求
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, window + 1)

            return {1, 0}
            """

            result = await self.redis.eval(
                lua_script,
                1,  # num_keys
                redis_key,
                now,
                window_seconds,
                max_requests,
            )

            allowed = bool(result[0])
            retry_after = int(result[1]) if not allowed else None

            return allowed, retry_after

        except Exception as e:
            logger.error(f"Rate limiter error (allowing request): {e}", exc_info=True)
            # 发生错误时允许请求通过，避免误杀
            return True, None


# 全局限流器实例（延迟初始化）
_rate_limiter = None


def get_rate_limiter():
    """获取或创建全局限流器实例"""
    global _rate_limiter
    if _rate_limiter is None:
        # 尝试获取 Redis 客户端
        redis_client = None
        try:
            import redis.asyncio as aioredis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            logger.info(f"Redis rate limiter initialized: {redis_url}")
        except ImportError:
            logger.warning("redis package not installed, rate limiting disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis for rate limiting: {e}")

        _rate_limiter = RedisRateLimiter(redis_client)

    return _rate_limiter


rate_limiter = get_rate_limiter()


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
