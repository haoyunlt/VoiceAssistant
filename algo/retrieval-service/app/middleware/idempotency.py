"""
Idempotency Middleware - 幂等性中间件
"""

import hashlib
import json
import logging
from collections.abc import Callable

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    幂等性中间件

    支持:
    - 基于 Idempotency-Key 头的幂等性保证
    - 缓存成功的响应
    - 可配置TTL
    """

    def __init__(
        self,
        app,
        redis_client: redis.Redis | None = None,
        ttl: int = 86400,  # 24小时
        whitelist_methods: set | None = None,
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.ttl = ttl
        self.whitelist_methods = whitelist_methods or {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 只对特定HTTP方法启用幂等性
        if request.method not in self.whitelist_methods:
            return await call_next(request)

        # 如果没有Redis客户端，跳过幂等性检查
        if not self.redis_client:
            return await call_next(request)

        # 获取幂等性键
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            # 没有提供幂等性键，直接处理请求
            return await call_next(request)

        # 生成缓存键
        cache_key = await self._generate_cache_key(request, idempotency_key)

        # 检查是否存在缓存的响应
        cached_response = await self._get_cached_response(cache_key)

        if cached_response:
            logger.info(f"Idempotency hit: {idempotency_key}")
            # 返回缓存的响应
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=dict(cached_response["headers"]),
                media_type=cached_response["media_type"],
            )

        # 处理请求
        response = await call_next(request)

        # 只缓存成功的响应（2xx状态码）
        if 200 <= response.status_code < 300:
            await self._cache_response(cache_key, response)

        return response

    async def _generate_cache_key(self, request: Request, idempotency_key: str) -> str:
        """
        生成缓存键

        包含:
        - Idempotency-Key
        - 请求路径
        - 请求方法
        - 租户ID（如果有）
        """
        # 读取请求体
        body = await request.body()

        # 生成请求签名
        data = {
            "idempotency_key": idempotency_key,
            "method": request.method,
            "path": request.url.path,
            "body": body.decode() if body else "",
        }

        # 添加租户ID（如果有）
        if hasattr(request.state, "tenant_id"):
            data["tenant_id"] = request.state.tenant_id

        signature = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

        return f"idempotency:{signature}"

    async def _get_cached_response(self, key: str) -> dict | None:
        """获取缓存的响应"""
        try:
            cached = await self.redis_client.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None

    async def _cache_response(self, key: str, response: Response):
        """缓存响应"""
        try:
            # 读取响应体
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # 缓存响应数据
            cached_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
                "body": body.decode(),
            }

            await self.redis_client.setex(
                key, self.ttl, json.dumps(cached_data, ensure_ascii=False)
            )

            # 重建响应体（因为已被消费）
            response.body_iterator = self._make_iterator(body)

        except Exception as e:
            logger.error(f"Error caching response: {e}")

    @staticmethod
    async def _make_iterator(body: bytes):
        """创建异步迭代器"""
        yield body
