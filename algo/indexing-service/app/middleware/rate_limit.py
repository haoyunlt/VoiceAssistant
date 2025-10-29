"""速率限制中间件"""
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件

    基于租户和IP的速率限制
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # 简单的内存存储（生产环境应使用Redis）
        self.request_counts = defaultdict(lambda: {"minute": [], "hour": []})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 获取租户ID（从header或query）
        tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id", "default")

        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"

        # 构建限流键
        rate_key = f"{tenant_id}:{client_ip}"

        # 当前时间
        now = time.time()

        # 清理过期记录
        self._cleanup_expired(rate_key, now)

        # 检查速率限制
        if self._is_rate_limited(rate_key, now):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {self.requests_per_minute}/min, {self.requests_per_hour}/hour",
                    "tenant_id": tenant_id,
                },
                headers={
                    "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
                    "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
                    "Retry-After": "60",
                }
            )

        # 记录请求
        self.request_counts[rate_key]["minute"].append(now)
        self.request_counts[rate_key]["hour"].append(now)

        # 继续处理请求
        response = await call_next(request)

        # 添加限流信息到响应头
        remaining_minute = self.requests_per_minute - len(self.request_counts[rate_key]["minute"])
        remaining_hour = self.requests_per_hour - len(self.request_counts[rate_key]["hour"])

        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, remaining_minute))
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, remaining_hour))

        return response

    def _cleanup_expired(self, rate_key: str, now: float):
        """清理过期的请求记录"""
        # 清理1分钟前的记录
        self.request_counts[rate_key]["minute"] = [
            ts for ts in self.request_counts[rate_key]["minute"]
            if now - ts < 60
        ]

        # 清理1小时前的记录
        self.request_counts[rate_key]["hour"] = [
            ts for ts in self.request_counts[rate_key]["hour"]
            if now - ts < 3600
        ]

    def _is_rate_limited(self, rate_key: str, now: float) -> bool:
        """检查是否超过速率限制"""
        minute_count = len(self.request_counts[rate_key]["minute"])
        hour_count = len(self.request_counts[rate_key]["hour"])

        return (
            minute_count >= self.requests_per_minute or
            hour_count >= self.requests_per_hour
        )
