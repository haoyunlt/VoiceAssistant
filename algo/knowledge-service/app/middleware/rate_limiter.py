"""
Rate Limiter Middleware
限流中间件
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    限流中间件
    
    基于Redis的令牌桶算法实现
    """

    def __init__(
        self,
        app,
        redis_client,
        requests_per_minute: int = 60,
        burst: int = 10,
        enabled: bool = True,
    ):
        """
        初始化限流中间件
        
        Args:
            app: FastAPI应用
            redis_client: Redis客户端
            requests_per_minute: 每分钟最大请求数
            burst: 突发请求数
            enabled: 是否启用
        """
        super().__init__(app)
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.enabled = enabled
        self.rate_per_second = requests_per_minute / 60.0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled or not self.redis:
            return await call_next(request)

        # 跳过健康检查和根路径
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # 获取客户端标识（IP或用户ID）
        client_id = self._get_client_id(request)
        
        # 检查限流
        allowed = await self._check_rate_limit(client_id)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute} requests per minute",
                },
            )

        response = await call_next(request)
        return response

    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用认证用户ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # 否则使用IP地址
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"

    async def _check_rate_limit(self, client_id: str) -> bool:
        """
        检查限流（令牌桶算法）
        
        Args:
            client_id: 客户端标识
            
        Returns:
            是否允许请求
        """
        try:
            key = f"rate_limit:{client_id}"
            now = time.time()
            
            # 使用Lua脚本保证原子性
            lua_script = """
            local key = KEYS[1]
            local rate = tonumber(ARGV[1])
            local burst = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local requested = 1
            
            -- 获取当前令牌数和最后更新时间
            local tokens = redis.call('HGET', key, 'tokens')
            local last_time = redis.call('HGET', key, 'last_time')
            
            if not tokens then
                tokens = burst
                last_time = now
            else
                tokens = tonumber(tokens)
                last_time = tonumber(last_time)
            end
            
            -- 计算新增令牌
            local elapsed = now - last_time
            local new_tokens = elapsed * rate
            tokens = math.min(burst, tokens + new_tokens)
            
            -- 检查是否有足够的令牌
            local allowed = 0
            if tokens >= requested then
                tokens = tokens - requested
                allowed = 1
            end
            
            -- 更新Redis
            redis.call('HSET', key, 'tokens', tokens)
            redis.call('HSET', key, 'last_time', now)
            redis.call('EXPIRE', key, 60)
            
            return allowed
            """
            
            result = await self.redis.eval(
                lua_script,
                1,
                key,
                str(self.rate_per_second),
                str(self.burst),
                str(now),
            )
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # 发生错误时允许请求通过
            return True

