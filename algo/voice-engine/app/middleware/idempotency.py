"""
幂等性中间件 - 防止重复请求
"""

import hashlib
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    幂等性中间件

    支持通过 X-Idempotency-Key 头来防止重复请求
    """

    def __init__(self, app, redis_client=None, ttl: int = 120):
        """
        初始化幂等性中间件

        Args:
            app: FastAPI 应用
            redis_client: Redis 客户端（用于存储幂等键）
            ttl: 幂等键的 TTL（秒），默认 120 秒
        """
        super().__init__(app)
        self.redis = redis_client
        self.ttl = ttl
        self._memory_cache = {}  # 如果没有 Redis，使用内存缓存

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""

        # 只对 POST/PUT/PATCH 请求启用幂等性
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)

        # 获取幂等键
        idempotency_key = request.headers.get("X-Idempotency-Key")

        if not idempotency_key:
            # 没有幂等键，直接处理请求
            return await call_next(request)

        # 构造缓存键
        cache_key = f"idempotency:{idempotency_key}:{request.url.path}"

        # 检查是否已经处理过
        cached_response = await self._get_cached_response(cache_key)

        if cached_response:
            logger.info(f"Idempotent request hit: {idempotency_key}")
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
            )

        # 处理请求
        response = await call_next(request)

        # 缓存响应（仅对成功的请求）
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            await self._cache_response(
                cache_key,
                {
                    "body": body,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                },
            )

            # 返回新的响应
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response

    async def _get_cached_response(self, key: str):
        """获取缓存的响应"""
        try:
            if self.redis:
                # 使用 Redis
                import json

                cached = await self.redis.get(key)
                if cached:
                    return json.loads(cached)
            else:
                # 使用内存缓存
                return self._memory_cache.get(key)
        except Exception as e:
            logger.error(f"Failed to get cached response: {e}")
            return None

    async def _cache_response(self, key: str, response_data: dict):
        """缓存响应"""
        try:
            if self.redis:
                # 使用 Redis
                import json

                await self.redis.setex(key, self.ttl, json.dumps(response_data))
            else:
                # 使用内存缓存（简化实现，生产环境应该使用 Redis）
                self._memory_cache[key] = response_data
        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
