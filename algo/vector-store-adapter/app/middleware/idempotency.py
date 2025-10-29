"""幂等性中间件 - 防止重复请求"""

import hashlib
import json
import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """幂等性中间件 - 基于 Idempotency-Key 防止重复请求"""

    def __init__(
        self,
        app,
        redis_client=None,
        ttl_seconds: int = 120,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._memory_cache = {}  # 备用内存缓存

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled:
            return await call_next(request)

        # 只对写操作启用幂等性
        if request.method not in ["POST", "PUT", "DELETE"]:
            return await call_next(request)

        # 跳过健康检查和指标端点
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return await call_next(request)

        # 获取幂等性键
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            # 如果没有提供幂等性键，生成一个（基于请求内容）
            idempotency_key = await self._generate_idempotency_key(request)

        # 检查是否已处理
        cached_response = await self._get_cached_response(idempotency_key)

        if cached_response:
            trace_id = getattr(request.state, "trace_id", "unknown")
            logger.info(
                "Idempotent request detected, returning cached response",
                extra={
                    "trace_id": trace_id,
                    "idempotency_key": idempotency_key,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers={"X-Idempotent-Replay": "true"},
            )

        # 处理请求
        response = await call_next(request)

        # 缓存响应（仅对成功的响应）
        if 200 <= response.status_code < 300:
            await self._cache_response(idempotency_key, response)

        return response

    async def _generate_idempotency_key(self, request: Request) -> str:
        """生成幂等性键（基于请求内容）"""
        # 读取请求体
        body = await request.body()

        # 生成键：method + path + body 的哈希
        content = f"{request.method}:{request.url.path}:{body.decode('utf-8', errors='ignore')}"
        key_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return f"auto:{key_hash}"

    async def _get_cached_response(self, idempotency_key: str) -> dict | None:
        """获取缓存的响应"""
        key = f"idempotency:{idempotency_key}"

        # 使用 Redis（如果可用）
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error(f"Redis get failed: {e}, falling back to memory")

        # 备用：使用内存缓存
        return self._memory_cache.get(key)

    async def _cache_response(self, idempotency_key: str, response: Response):
        """缓存响应"""
        key = f"idempotency:{idempotency_key}"

        # 读取响应体
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        # 解码响应
        try:
            body_json = json.loads(response_body.decode())
        except Exception:
            # 如果无法解码，不缓存
            return

        cached_data = {
            "status_code": response.status_code,
            "body": body_json,
        }

        # 使用 Redis（如果可用）
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    json.dumps(cached_data),
                )
                return
            except Exception as e:
                logger.error(f"Redis set failed: {e}, falling back to memory")

        # 备用：使用内存缓存
        self._memory_cache[key] = cached_data
