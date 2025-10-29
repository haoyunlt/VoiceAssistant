"""
Idempotency Middleware
幂等性中间件
"""

import hashlib
import json
import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    幂等性中间件

    使用Redis存储请求结果，相同的幂等键返回缓存的响应
    """

    def __init__(
        self,
        app,
        redis_client,
        ttl: int = 120,
        enabled: bool = True,
    ):
        """
        初始化幂等性中间件

        Args:
            app: FastAPI应用
            redis_client: Redis客户端
            ttl: 缓存TTL（秒）
            enabled: 是否启用
        """
        super().__init__(app)
        self.redis = redis_client
        self.ttl = ttl
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled or not self.redis:
            return await call_next(request)

        # 只对POST/PUT/PATCH请求启用幂等性
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)

        # 获取幂等键
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # 如果没有提供幂等键，生成一个基于请求内容的键
            idempotency_key = await self._generate_idempotency_key(request)

        if not idempotency_key:
            # 无法生成幂等键，跳过幂等性检查
            return await call_next(request)

        # 检查是否有缓存的响应
        cached_response = await self._get_cached_response(idempotency_key)
        if cached_response:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response.get("media_type", "application/json"),
            )

        # 执行请求
        response = await call_next(request)

        # 缓存响应（只缓存成功的响应）
        if 200 <= response.status_code < 300:
            await self._cache_response(idempotency_key, response)

        return response

    async def _generate_idempotency_key(self, request: Request) -> str:
        """
        生成幂等键

        基于请求路径、方法和body生成hash
        """
        try:
            body = await request.body()
            content = f"{request.method}:{request.url.path}:{body.decode('utf-8')}"
            key_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            return f"auto:{key_hash}"
        except Exception as e:
            logger.warning(f"Failed to generate idempotency key: {e}")
            return ""

    async def _get_cached_response(self, idempotency_key: str):
        """获取缓存的响应"""
        try:
            cache_key = f"idempotency:{idempotency_key}"
            cached = await self.redis.get(cache_key)

            if cached:
                return json.loads(cached)

            return None

        except Exception as e:
            logger.error(f"Failed to get cached response: {e}")
            return None

    async def _cache_response(self, idempotency_key: str, response: Response):
        """缓存响应"""
        try:
            # 读取响应body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # 构造缓存数据
            cache_data = {
                "body": body.decode("utf-8"),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
            }

            cache_key = f"idempotency:{idempotency_key}"
            await self.redis.setex(
                cache_key,
                self.ttl,
                json.dumps(cache_data, ensure_ascii=False),
            )

            logger.debug(f"Cached response for idempotency key: {idempotency_key}")

            # 重建响应body
            response.body_iterator = self._create_body_iterator(body)

        except Exception as e:
            logger.error(f"Failed to cache response: {e}")

    async def _create_body_iterator(self, body: bytes):
        """创建body迭代器"""
        yield body

