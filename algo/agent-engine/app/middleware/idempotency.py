"""
幂等性中间件
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse


class IdempotencyStore:
    """
    幂等性存储（内存实现，生产环境应使用 Redis）
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        初始化幂等性存储

        Args:
            ttl_seconds: 幂等键 TTL（秒）
        """
        self.store = {}
        self.ttl_seconds = ttl_seconds
        self.lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[dict]:
        """获取幂等性响应"""
        async with self.lock:
            data = self.store.get(key)
            if data:
                # 检查是否过期
                if time.time() - data["timestamp"] < self.ttl_seconds:
                    return data["response"]
                else:
                    # 清理过期数据
                    del self.store[key]
            return None

    async def set(self, key: str, response: dict):
        """保存幂等性响应"""
        async with self.lock:
            self.store[key] = {
                "response": response,
                "timestamp": time.time()
            }

    async def cleanup(self):
        """清理过期数据"""
        async with self.lock:
            now = time.time()
            expired_keys = [
                key for key, data in self.store.items()
                if now - data["timestamp"] >= self.ttl_seconds
            ]
            for key in expired_keys:
                del self.store[key]


# 全局幂等性存储
idempotency_store = IdempotencyStore()


class IdempotencyMiddleware:
    """
    幂等性中间件

    基于幂等键（Idempotency-Key）防止重复请求
    """

    def __init__(self, ttl_seconds: int = 300):
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
        if request.url.path in skip_paths:
            return False

        return True

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

        key_parts = [
            tenant_id,
            user_id,
            request.url.path,
            idempotency_key
        ]

        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()

    async def __call__(self, request: Request, call_next):
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
                headers={
                    **cached_response.get("headers", {}),
                    "X-Idempotency-Replay": "true"
                }
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
                "headers": dict(response.headers)
            }
            await idempotency_store.set(full_key, cached_data)

            # 重建响应
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        return response


def idempotent(ttl_seconds: int = 300):
    """
    路由级别的幂等性装饰器

    Args:
        ttl_seconds: 幂等键有效期

    Returns:
        装饰器函数
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # TODO: 实现路由级别的幂等性逻辑
            return await func(*args, **kwargs)
        return wrapper
    return decorator
