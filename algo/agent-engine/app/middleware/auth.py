"""Authentication middleware and permission helpers."""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import HTTPException, Request, status  # type: ignore[import]
from fastapi.security import (  # type: ignore[import]
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.auth.jwt_manager import get_jwt_manager
from app.auth.rbac import Permission, get_rbac_manager

UserContext = dict[str, Any]


security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials) -> UserContext:
    """Verify JWT token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    token = credentials.credentials
    jwt_manager = get_jwt_manager()

    try:
        claims = jwt_manager.validate_token(token)
        if claims is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        return {
            "user_id": claims.user_id,
            "username": claims.username,
            "email": claims.email,
            "roles": claims.roles,
        }
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(err),
        ) from err


def require_permission(permission: Permission) -> Callable[[Request], Awaitable[UserContext]]:
    """Decorator to require a specific permission"""

    async def permission_checker(request: Request) -> UserContext:
        # Get user from request state
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        rbac_manager = get_rbac_manager()
        roles = user.get("roles", [])

        if not rbac_manager.check_user_permission(roles, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}",
            )

        return cast(UserContext, user)

    return permission_checker


def require_any_permission(
    permissions: list[Permission],
) -> Callable[[Request], Awaitable[UserContext]]:
    """Decorator to require any of the specified permissions"""

    async def permission_checker(request: Request) -> UserContext:
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        rbac_manager = get_rbac_manager()
        roles = user.get("roles", [])

        has_permission = any(
            rbac_manager.check_user_permission(roles, perm) for perm in permissions
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required any of: {[p.value for p in permissions]}",
            )

        return cast(UserContext, user)

    return permission_checker


def require_role(role: str) -> Callable[[Request], Awaitable[UserContext]]:
    """Decorator to require a specific role"""

    async def role_checker(request: Request) -> UserContext:
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        roles = user.get("roles", [])

        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}",
            )

        return cast(UserContext, user)

    return role_checker


class AuthMiddleware:
    """Authentication middleware"""

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        if scope["type"] == "http":
            request = Request(scope, receive)

            # Extract token from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                jwt_manager = get_jwt_manager()

                try:
                    claims = jwt_manager.validate_token(token)
                    if claims is not None:
                        # Store user info in request state
                        request.state.user = {
                            "user_id": claims.user_id,
                            "username": claims.username,
                            "email": claims.email,
                            "roles": claims.roles,
                        }
                except ValueError:
                    pass  # Invalid token, continue without user

        await self.app(scope, receive, send)
