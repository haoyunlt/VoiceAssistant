"""
Authentication Middleware - API认证中间件
"""

import logging
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件

    支持:
    - API Key 认证 (Authorization: Bearer <api_key>)
    - 可配置白名单路径
    """

    def __init__(
        self,
        app,
        api_keys: Optional[set] = None,
        whitelist_paths: Optional[set] = None,
    ):
        super().__init__(app)
        self.api_keys = api_keys or set()
        self.whitelist_paths = whitelist_paths or {
            "/health",
            "/ready",
            "/metrics",
            "/docs",
            "/openapi.json",
            "/redoc",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 白名单路径跳过认证
        if request.url.path in self.whitelist_paths:
            return await call_next(request)

        # 检查认证头
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 验证 Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format. Expected: Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"},
            )

        api_key = parts[1]

        # 如果配置了API keys，则验证
        if self.api_keys and api_key not in self.api_keys:
            logger.warning(f"Invalid API key attempt from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        # 将认证信息存储到请求状态
        request.state.api_key = api_key

        # 继续处理请求
        response = await call_next(request)
        return response
