"""
Authentication Middleware for FastAPI
"""

from typing import List, Optional

from app.auth.jwt_manager import get_jwt_manager
from app.auth.rbac import Permission, get_rbac_manager
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


async def verify_token(credentials: HTTPAuthorizationCredentials) -> dict:
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
        return {
            "user_id": claims.user_id,
            "username": claims.username,
            "email": claims.email,
            "roles": claims.roles,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


def require_permission(permission: Permission):
    """Decorator to require a specific permission"""

    async def permission_checker(request: Request):
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

        return user

    return permission_checker


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the specified permissions"""

    async def permission_checker(request: Request):
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

        return user

    return permission_checker


def require_role(role: str):
    """Decorator to require a specific role"""

    async def role_checker(request: Request):
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

        return user

    return role_checker


class AuthMiddleware:
    """Authentication middleware"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)

            # Extract token from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                jwt_manager = get_jwt_manager()

                try:
                    claims = jwt_manager.validate_token(token)
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
