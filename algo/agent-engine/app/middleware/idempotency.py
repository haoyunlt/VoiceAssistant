"""幂等性中间件 - 基于 Redis 的生产级实现。"""

import hashlib
import json
import logging
import os
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import Request, Response  # type: ignore[import]
from fastapi.responses import JSONResponse  # type: ignore[import]

logger = logging.getLogger(__name__)


class RedisIdempotencyStore:
    """
    基于 Redis 的幂等性存储

    使用 Redis 字符串类型存储响应，自动过期，支持分布式部署
    """

    def __init__(self, redis_client=None, ttl_seconds: int = 300) -> None:
        """
        初始化幂等性存储

        Args:
            redis_client: Redis 客户端实例
            ttl_seconds: 幂等键 TTL（秒）
        """
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self._warned_no_redis = False

    async def get(self, key: str) -> dict[str, Any] | None:
        """
        获取幂等性响应

        Args:
            key: 幂等键

        Returns:
            缓存的响应数据，如果不存在或已过期则返回 None
        """
        if not self.redis:
            # Redis 不可用时返回 None（不缓存）
            if not self._warned_no_redis:
                logger.warning("Redis not available, idempotency check disabled")
                self._warned_no_redis = True
            return None

        try:
            redis_key = f"idempotency:{key}"
            data = await self.redis.get(redis_key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Idempotency store get error: {e}", exc_info=True)
            return None

    async def set(self, key: str, response: dict[str, Any]) -> None:
        """
        保存幂等性响应

        Args:
            key: 幂等键
            response: 响应数据
        """
        if not self.redis:
            return

        try:
            redis_key = f"idempotency:{key}"
            data = json.dumps(response, default=str)

            # 使用 SETEX 设置值和过期时间
            await self.redis.setex(redis_key, self.ttl_seconds, data)

        except Exception as e:
            logger.error(f"Idempotency store set error: {e}", exc_info=True)


# 全局幂等性存储（延迟初始化）
_idempotency_store = None


def get_idempotency_store(ttl_seconds: int = 300):
    """获取或创建全局幂等性存储实例"""
    global _idempotency_store
    if _idempotency_store is None:
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
            logger.info(f"Redis idempotency store initialized: {redis_url}")
        except ImportError:
            logger.warning("redis package not installed, idempotency check disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis for idempotency: {e}")

        _idempotency_store = RedisIdempotencyStore(redis_client, ttl_seconds)

    return _idempotency_store


idempotency_store = get_idempotency_store()


class IdempotencyMiddleware:
    """
    幂等性中间件

    基于幂等键（Idempotency-Key）防止重复请求
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        """
        初始化幂等性中间件

        Args:
            ttl_seconds: 幂等键有效期（秒）
        """
        self.ttl_seconds = ttl_seconds

    def _should_check_idempotency(self, request: Request) -> bool:
        """判断是否需要检查幂等性"""
        # 只对 POST/PUT/PATCH 请求检查幂等性
        if request.method not in ["POST", "PUT", "PATCH"]:
            return False

        # 跳过特定路径
        skip_paths = ["/health", "/ready", "/metrics"]
        return request.url.path not in skip_paths

    def _generate_key(self, request: Request, idempotency_key: str) -> str:
        """
        生成幂等键

        Args:
            request: 请求对象
            idempotency_key: 客户端提供的幂等键

        Returns:
            完整的幂等键
        """
        # 组合租户 ID、用户 ID、路径和幂等键
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        user_id = request.headers.get("X-User-ID", "anonymous")

        key_parts = [tenant_id, user_id, request.url.path, idempotency_key]

        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()

    async def __call__(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理请求"""
        # 检查是否需要幂等性检查
        if not self._should_check_idempotency(request):
            return await call_next(request)

        # 获取幂等键
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # 如果没有幂等键，正常处理请求
            return await call_next(request)

        # 生成完整的幂等键
        full_key = self._generate_key(request, idempotency_key)

        # 检查是否已有缓存的响应
        cached_response = await idempotency_store.get(full_key)
        if cached_response:
            # 返回缓存的响应
            return JSONResponse(
                status_code=cached_response["status_code"],
                content=cached_response["content"],
                headers={**cached_response.get("headers", {}), "X-Idempotency-Replay": "true"},
            )

        # 处理请求
        response = await call_next(request)

        # 缓存成功的响应
        if 200 <= response.status_code < 300:
            # 读取响应内容
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # 保存到缓存
            cached_data = {
                "status_code": response.status_code,
                "content": json.loads(response_body) if response_body else {},
                "headers": dict(response.headers),
            }
            await idempotency_store.set(full_key, cached_data)

            # 重建响应
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response


def idempotent(
    ttl_seconds: int = 300,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    路由级别的幂等性装饰器

    Args:
        ttl_seconds: 幂等键有效期

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        _ = ttl_seconds  # 保留参数以便后续扩展

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # TODO: 实现路由级别的幂等性逻辑
            return await func(*args, **kwargs)

        return wrapper

    return decorator
