"""
限流中间件 - 租户级别和用户级别限流
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    限流中间件

    支持：
    - 租户级别限流（基于 X-Tenant-ID）
    - 用户级别限流（基于 X-User-ID）
    - IP 级别限流（fallback）
    """

    def __init__(
        self,
        app,
        redis_client=None,
        tenant_limit: int = 100,  # 每分钟
        user_limit: int = 20,  # 每分钟
        ip_limit: int = 10,  # 每分钟
    ):
        """
        初始化限流中间件

        Args:
            app: FastAPI 应用
            redis_client: Redis 客户端
            tenant_limit: 租户级别限制（请求/分钟）
            user_limit: 用户级别限制（请求/分钟）
            ip_limit: IP 级别限制（请求/分钟）
        """
        super().__init__(app)
        self.redis = redis_client
        self.tenant_limit = tenant_limit
        self.user_limit = user_limit
        self.ip_limit = ip_limit
        self._memory_cache = {}  # 内存缓存（如果没有 Redis）

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""

        # 获取租户 ID、用户 ID 和 IP
        tenant_id = request.headers.get("X-Tenant-ID")
        user_id = request.headers.get("X-User-ID")
        client_ip = request.client.host if request.client else "unknown"

        # 检查限流
        rate_limit_result = await self._check_rate_limit(
            tenant_id, user_id, client_ip
        )

        if not rate_limit_result["allowed"]:
            logger.warning(
                f"Rate limit exceeded: {rate_limit_result['identifier']}, "
                f"limit={rate_limit_result['limit']}, "
                f"remaining=0"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {rate_limit_result['limit']} requests per minute.",
                    "retry_after": rate_limit_result["retry_after"],
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_limit_result["reset_at"]),
                    "Retry-After": str(rate_limit_result["retry_after"]),
                },
            )

        # 处理请求
        response = await call_next(request)

        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(rate_limit_result["limit"])
        response.headers["X-RateLimit-Remaining"] = str(
            rate_limit_result["remaining"]
        )
        response.headers["X-RateLimit-Reset"] = str(rate_limit_result["reset_at"])

        return response

    async def _check_rate_limit(
        self, tenant_id: str, user_id: str, client_ip: str
    ) -> dict:
        """
        检查限流

        优先级：租户 > 用户 > IP
        """

        # 确定限流维度
        if tenant_id:
            identifier = f"tenant:{tenant_id}"
            limit = self.tenant_limit
        elif user_id:
            identifier = f"user:{user_id}"
            limit = self.user_limit
        else:
            identifier = f"ip:{client_ip}"
            limit = self.ip_limit

        # 检查限流
        current_minute = int(time.time() / 60)
        cache_key = f"rate_limit:{identifier}:{current_minute}"

        try:
            if self.redis:
                # 使用 Redis
                count = await self.redis.incr(cache_key)
                if count == 1:
                    await self.redis.expire(cache_key, 60)  # 60 秒过期
            else:
                # 使用内存缓存
                count = self._memory_cache.get(cache_key, 0) + 1
                self._memory_cache[cache_key] = count

            remaining = max(0, limit - count)
            allowed = count <= limit

            reset_at = (current_minute + 1) * 60
            retry_after = reset_at - int(time.time())

            return {
                "allowed": allowed,
                "identifier": identifier,
                "limit": limit,
                "remaining": remaining,
                "reset_at": reset_at,
                "retry_after": retry_after,
            }

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}", exc_info=True)
            # 失败时允许请求通过
            return {
                "allowed": True,
                "identifier": identifier,
                "limit": limit,
                "remaining": limit,
                "reset_at": (current_minute + 1) * 60,
                "retry_after": 60,
            }
