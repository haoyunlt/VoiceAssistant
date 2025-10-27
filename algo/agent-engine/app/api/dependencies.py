"""
API 依赖注入
"""

from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ServiceNotInitializedException,
)


def get_agent_engine(request: Request):
    """
    获取 Agent Engine 实例

    Args:
        request: FastAPI Request

    Returns:
        AgentEngine 实例

    Raises:
        HTTPException: 服务未初始化
    """
    if not hasattr(request.app.state, "agent_engine"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent Engine not initialized"
        )
    return request.app.state.agent_engine


def get_memory_manager(request: Request):
    """
    获取 Memory Manager 实例

    Args:
        request: FastAPI Request

    Returns:
        Memory Manager 实例

    Raises:
        HTTPException: 服务未初始化
    """
    if not hasattr(request.app.state, "memory_manager"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory Manager not initialized"
        )
    return request.app.state.memory_manager


def get_tool_registry(request: Request):
    """
    获取 Tool Registry 实例

    Args:
        request: FastAPI Request

    Returns:
        Tool Registry 实例

    Raises:
        HTTPException: 服务未初始化
    """
    agent_engine = get_agent_engine(request)
    if not hasattr(agent_engine, "tool_registry") or agent_engine.tool_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tool Registry not initialized"
        )
    return agent_engine.tool_registry


def get_config_manager(request: Request):
    """
    获取 Config Manager 实例

    Args:
        request: FastAPI Request

    Returns:
        Config Manager 实例（可能为 None）
    """
    return getattr(request.app.state, "config_manager", None)


def get_request_id(
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID")
) -> str:
    """
    获取或生成请求 ID

    Args:
        x_request_id: 请求头中的请求 ID

    Returns:
        请求 ID
    """
    if x_request_id:
        return x_request_id

    # 生成新的请求 ID
    import uuid
    return str(uuid.uuid4())


def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> Optional[str]:
    """
    从请求头获取租户 ID

    Args:
        x_tenant_id: 租户 ID

    Returns:
        租户 ID
    """
    return x_tenant_id


def get_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Optional[str]:
    """
    从请求头获取用户 ID

    Args:
        x_user_id: 用户 ID

    Returns:
        用户 ID
    """
    return x_user_id


# 认证依赖（占位实现）
async def verify_token(
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    验证访问令牌

    Args:
        authorization: Authorization 头

    Returns:
        用户信息字典

    Raises:
        HTTPException: 认证失败
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 提取 token
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # TODO: 实际的 token 验证逻辑
        # 这里应该调用 JWT 验证或其他认证服务
        # from app.auth.jwt_manager import verify_jwt
        # user_info = verify_jwt(token)

        # 临时返回模拟数据
        user_info = {
            "user_id": "temp_user",
            "tenant_id": "temp_tenant",
            "permissions": ["agent:execute", "tool:register", "memory:read"]
        }

        return user_info

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def check_permissions(required_permissions: list):
    """
    检查权限装饰器

    Args:
        required_permissions: 需要的权限列表

    Returns:
        权限检查函数
    """
    async def permission_checker(user: dict = Depends(verify_token)):
        user_permissions = user.get("permissions", [])

        # 检查是否有所有需要的权限
        missing_permissions = [
            perm for perm in required_permissions
            if perm not in user_permissions
        ]

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing_permissions)}"
            )

        return None

    return permission_checker


# 可选的认证依赖（不强制要求认证）
async def optional_verify_token(
    authorization: Optional[str] = Header(None)
) -> Optional[dict]:
    """
    可选的令牌验证

    Args:
        authorization: Authorization 头

    Returns:
        用户信息字典或 None
    """
    if not authorization:
        return None

    try:
        return await verify_token(authorization)
    except HTTPException:
        return None
