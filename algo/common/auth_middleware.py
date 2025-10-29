"""
统一的认证中间件

支持：
- JWT Token 验证
- 服务间认证
- 租户/用户信息注入
- 可选认证（健康检查端点）
"""

import logging
import os
from collections.abc import Callable

import httpx
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件

    验证 JWT Token 并注入用户信息到 request.state
    """

    def __init__(
        self,
        app,
        identity_service_url: str,
        excluded_paths: set[str] | None = None,
        require_auth: bool = True,
        timeout: float = 2.0,
    ):
        """
        初始化认证中间件

        Args:
            app: FastAPI 应用实例
            identity_service_url: 身份认证服务URL
            excluded_paths: 排除的路径集合（不需要认证）
            require_auth: 是否强制要求认证
            timeout: 认证服务调用超时（秒）
        """
        super().__init__(app)
        self.identity_service_url = identity_service_url.rstrip("/")
        self.require_auth = require_auth
        self.timeout = timeout

        # 默认排除的路径
        self.excluded_paths = excluded_paths or {
            "/health",
            "/ready",
            "/readiness",
            "/liveness",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

        # 是否启用降级模式（认证服务不可用时）
        self.fail_open = os.getenv("AUTH_FAIL_OPEN", "false").lower() == "true"

        logger.info(
            f"Auth middleware initialized: "
            f"identity_service={self.identity_service_url}, "
            f"require_auth={self.require_auth}, "
            f"fail_open={self.fail_open}"
        )

    async def dispatch(self, request: Request, call_next: Callable):
        """处理请求"""
        # 检查是否需要认证
        if self._should_skip_auth(request):
            return await call_next(request)

        # 提取 Token
        token = self._extract_token(request)

        if not token:
            if self.require_auth:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "AuthenticationError",
                        "message": "Missing or invalid authorization header",
                    },
                )
            else:
                # 可选认证，继续处理
                return await call_next(request)

        # 验证 Token
        try:
            user_info = await self._verify_token(token)

            if user_info:
                # 注入用户信息到 request.state
                request.state.user_id = user_info.get("user_id")
                request.state.username = user_info.get("username")
                request.state.email = user_info.get("email")
                request.state.tenant_id = user_info.get("tenant_id")
                request.state.roles = user_info.get("roles", [])
                request.state.authenticated = True

                logger.debug(
                    f"User authenticated: user_id={request.state.user_id}, "
                    f"tenant_id={request.state.tenant_id}"
                )
            else:
                if self.require_auth:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={
                            "error": "AuthenticationError",
                            "message": "Invalid or expired token",
                        },
                    )

        except httpx.TimeoutException:
            logger.error("Authentication service timeout")
            if self.fail_open:
                # 降级模式：允许通过
                logger.warning("Auth service timeout, fail-open mode enabled")
                request.state.authenticated = False
            else:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "error": "ServiceUnavailableError",
                        "message": "Authentication service unavailable",
                    },
                )

        except Exception as e:
            logger.error(f"Authentication failed: {e}", exc_info=True)
            if self.require_auth:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "AuthenticationError",
                        "message": "Authentication failed",
                    },
                )

        return await call_next(request)

    def _should_skip_auth(self, request: Request) -> bool:
        """判断是否跳过认证"""
        path = request.url.path

        # 检查排除路径
        if path in self.excluded_paths:
            return True

        # 检查路径前缀
        return bool(any(path.startswith(prefix) for prefix in ["/static/", "/docs", "/redoc"]))

    def _extract_token(self, request: Request) -> str | None:
        """
        从请求中提取 Token

        支持：
        1. Authorization: Bearer <token>
        2. X-API-Key: <token>
        3. Cookie: token=<token>
        """
        # 1. Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # 2. X-API-Key header（服务间调用）
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return api_key

        # 3. Cookie
        token = request.cookies.get("token", "")
        if token:
            return token

        return None

    async def _verify_token(self, token: str) -> dict | None:
        """
        验证 Token

        Args:
            token: JWT Token

        Returns:
            用户信息字典，验证失败返回 None
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.identity_service_url}/api/v1/auth/verify",
                    json={"token": token},
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(
                        f"Token verification failed: status={response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise


class RequireRole:
    """
    角色权限装饰器

    Usage:
        @app.get("/admin")
        @RequireRole("admin")
        async def admin_endpoint():
            ...
    """

    def __init__(self, *roles: str):
        """
        初始化角色要求

        Args:
            *roles: 允许的角色列表
        """
        self.required_roles = set(roles)

    def __call__(self, func: Callable):
        """装饰器实现"""
        import functools

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取request（FastAPI会注入）
            request = kwargs.get("request")
            if not request:
                # 尝试从args中查找
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                raise AuthorizationError("Request object not found")

            # 检查认证
            if not getattr(request.state, "authenticated", False):
                raise AuthenticationError("Not authenticated")

            # 检查角色
            user_roles = set(getattr(request.state, "roles", []))
            if not self.required_roles.intersection(user_roles):
                raise AuthorizationError(
                    f"Required roles: {self.required_roles}, user roles: {user_roles}"
                )

            return await func(*args, **kwargs)

        return wrapper


def get_current_user(request: Request) -> dict:
    """
    获取当前认证用户信息

    Args:
        request: FastAPI Request 对象

    Returns:
        用户信息字典

    Raises:
        AuthenticationError: 如果用户未认证
    """
    if not getattr(request.state, "authenticated", False):
        raise AuthenticationError("Not authenticated")

    return {
        "user_id": getattr(request.state, "user_id", None),
        "username": getattr(request.state, "username", None),
        "email": getattr(request.state, "email", None),
        "tenant_id": getattr(request.state, "tenant_id", None),
        "roles": getattr(request.state, "roles", []),
    }


def get_current_tenant_id(request: Request) -> str | None:
    """
    获取当前租户ID

    Args:
        request: FastAPI Request 对象

    Returns:
        租户ID，如果未认证则返回 None
    """
    return getattr(request.state, "tenant_id", None)


# 依赖注入（FastAPI Depends）


def require_auth(request: Request) -> dict:
    """
    FastAPI 依赖：要求认证

    Usage:
        @app.get("/protected")
        async def protected_endpoint(user: dict = Depends(require_auth)):
            return {"user": user}
    """
    return get_current_user(request)


def optional_auth(request: Request) -> dict | None:
    """
    FastAPI 依赖：可选认证

    Usage:
        @app.get("/public")
        async def public_endpoint(user: Optional[dict] = Depends(optional_auth)):
            if user:
                return {"message": "Hello", "user": user["username"]}
            return {"message": "Hello, guest"}
    """
    try:
        return get_current_user(request)
    except AuthenticationError:
        return None
