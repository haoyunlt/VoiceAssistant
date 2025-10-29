"""
Authorization Service

授权服务，负责 RBAC 权限控制和审计日志
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """资源类型"""
    KNOWLEDGE_BASE = "kb"
    DOCUMENT = "doc"
    CHUNK = "chunk"
    VERSION = "version"


class Action(str, Enum):
    """操作类型"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class Effect(str, Enum):
    """效果"""
    ALLOW = "allow"
    DENY = "deny"


class Permission:
    """权限"""

    def __init__(
        self,
        resource: str,
        action: str,
        effect: str = "allow",
        conditions: Optional[Dict[str, Any]] = None
    ):
        self.resource = resource  # kb:123, doc:456, *
        self.action = action      # read, write, delete, admin
        self.effect = effect      # allow, deny
        self.conditions = conditions or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "resource": self.resource,
            "action": self.action,
            "effect": self.effect,
            "conditions": self.conditions
        }


class Role:
    """角色"""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        permissions: List[Permission],
        tenant_id: str,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.name = name
        self.description = description
        self.permissions = permissions
        self.tenant_id = tenant_id
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def create_administrator(cls, tenant_id: str) -> "Role":
        """创建管理员角色"""
        return cls(
            id=f"role_{uuid4()}",
            name="Administrator",
            description="Full access to all resources",
            permissions=[
                Permission(resource="*", action="admin", effect="allow")
            ],
            tenant_id=tenant_id
        )

    @classmethod
    def create_editor(cls, tenant_id: str) -> "Role":
        """创建编辑者角色"""
        return cls(
            id=f"role_{uuid4()}",
            name="Editor",
            description="Can read and write knowledge bases and documents",
            permissions=[
                Permission(resource="kb:*", action="write", effect="allow"),
                Permission(resource="doc:*", action="write", effect="allow")
            ],
            tenant_id=tenant_id
        )

    @classmethod
    def create_viewer(cls, tenant_id: str) -> "Role":
        """创建查看者角色"""
        return cls(
            id=f"role_{uuid4()}",
            name="Viewer",
            description="Can only read knowledge bases and documents",
            permissions=[
                Permission(resource="kb:*", action="read", effect="allow"),
                Permission(resource="doc:*", action="read", effect="allow")
            ],
            tenant_id=tenant_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions],
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class UserRole:
    """用户角色关联"""

    def __init__(
        self,
        id: str,
        user_id: str,
        role_id: str,
        tenant_id: str,
        resource: Optional[str] = None,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ):
        self.id = id
        self.user_id = user_id
        self.role_id = role_id
        self.tenant_id = tenant_id
        self.resource = resource  # 可选：限定角色作用的资源范围
        self.created_at = created_at or datetime.utcnow()
        self.expires_at = expires_at


class AuditLog:
    """审计日志"""

    def __init__(
        self,
        id: str,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        details: str,
        ip: str,
        user_agent: str,
        status: str,
        error: str = "",
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.action = action
        self.resource = resource
        self.details = details
        self.ip = ip
        self.user_agent = user_agent
        self.status = status
        self.error = error
        self.created_at = created_at or datetime.utcnow()

    @classmethod
    def create(
        cls,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        details: Dict[str, Any],
        ip: str,
        user_agent: str,
        status: str = "success",
        error: str = ""
    ) -> "AuditLog":
        """创建审计日志"""
        return cls(
            id=f"audit_{uuid4()}",
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            details=json.dumps(details),
            ip=ip,
            user_agent=user_agent,
            status=status,
            error=error
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat()
        }


class AuthzService:
    """授权服务"""

    def __init__(self, redis_client: Optional[Any] = None):
        """初始化授权服务

        Args:
            redis_client: Redis 客户端（用于权限缓存）
        """
        self.redis = redis_client
        self._roles_cache: Dict[str, Role] = {}
        self._user_roles_cache: Dict[str, List[str]] = {}  # user_id -> [role_id]
        self._audit_logs: List[AuditLog] = []

        # 初始化内置角色
        self._init_builtin_roles()

    def _init_builtin_roles(self) -> None:
        """初始化内置角色"""
        # 创建默认租户的内置角色
        default_tenant = "default"
        self._roles_cache["admin"] = Role.create_administrator(default_tenant)
        self._roles_cache["editor"] = Role.create_editor(default_tenant)
        self._roles_cache["viewer"] = Role.create_viewer(default_tenant)

    async def check_permission(
        self,
        user_id: str,
        tenant_id: str,
        resource: str,
        action: str
    ) -> bool:
        """检查权限

        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID
            resource: 资源（如 kb:123, doc:456）
            action: 操作（read, write, delete, admin）

        Returns:
            是否有权限
        """
        # 1. 尝试从缓存获取
        cache_key = f"perm:{user_id}:{resource}:{action}"
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached == "1"
            except Exception as e:
                logger.warning(f"Failed to get from cache: {e}")

        # 2. 获取用户角色
        roles = await self._get_user_roles(user_id, tenant_id)

        # 3. 评估权限
        allowed = self._evaluate_permissions(roles, resource, action)

        # 4. 缓存结果（TTL=5分钟）
        if self.redis:
            try:
                await self.redis.setex(cache_key, 300, "1" if allowed else "0")
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")

        return allowed

    async def grant_role(
        self,
        user_id: str,
        role_id: str,
        tenant_id: str,
        resource: Optional[str] = None
    ) -> bool:
        """授予角色

        Args:
            user_id: 用户 ID
            role_id: 角色 ID
            tenant_id: 租户 ID
            resource: 限定资源范围（可选）

        Returns:
            是否成功
        """
        if user_id not in self._user_roles_cache:
            self._user_roles_cache[user_id] = []

        if role_id not in self._user_roles_cache[user_id]:
            self._user_roles_cache[user_id].append(role_id)
            logger.info(f"Granted role {role_id} to user {user_id}")
            return True

        return False

    async def revoke_role(self, user_id: str, role_id: str) -> bool:
        """撤销角色

        Args:
            user_id: 用户 ID
            role_id: 角色 ID

        Returns:
            是否成功
        """
        if user_id in self._user_roles_cache:
            if role_id in self._user_roles_cache[user_id]:
                self._user_roles_cache[user_id].remove(role_id)
                logger.info(f"Revoked role {role_id} from user {user_id}")
                return True

        return False

    async def log_action(
        self,
        tenant_id: str,
        user_id: str,
        action: str,
        resource: str,
        details: Dict[str, Any],
        ip: str,
        user_agent: str,
        status: str = "success",
        error: str = ""
    ) -> None:
        """记录审计日志

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID
            action: 操作
            resource: 资源
            details: 详细信息
            ip: IP 地址
            user_agent: User Agent
            status: 状态
            error: 错误信息
        """
        audit_log = AuditLog.create(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource=resource,
            details=details,
            ip=ip,
            user_agent=user_agent,
            status=status,
            error=error
        )

        self._audit_logs.append(audit_log)
        logger.info(f"Audit log: {action} on {resource} by {user_id} - {status}")

    async def get_audit_logs(
        self,
        tenant_id: str,
        offset: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[AuditLog]:
        """获取审计日志

        Args:
            tenant_id: 租户 ID
            offset: 偏移量
            limit: 数量限制
            filters: 过滤条件

        Returns:
            审计日志列表
        """
        logs = [log for log in self._audit_logs if log.tenant_id == tenant_id]

        # 应用过滤器
        if filters:
            if "user_id" in filters:
                logs = [log for log in logs if log.user_id == filters["user_id"]]
            if "action" in filters:
                logs = [log for log in logs if log.action == filters["action"]]

        # 按时间倒序
        logs.sort(key=lambda log: log.created_at, reverse=True)

        return logs[offset:offset+limit]

    async def _get_user_roles(self, user_id: str, tenant_id: str) -> List[Role]:
        """获取用户角色"""
        role_ids = self._user_roles_cache.get(user_id, [])
        roles = []
        for role_id in role_ids:
            role = self._roles_cache.get(role_id)
            if role and role.tenant_id == tenant_id:
                roles.append(role)
        return roles

    def _evaluate_permissions(
        self,
        roles: List[Role],
        resource: str,
        action: str
    ) -> bool:
        """评估权限（Deny 优先）"""
        # 1. 检查 Deny
        for role in roles:
            for perm in role.permissions:
                if self._match_resource(perm.resource, resource) and \
                   self._match_action(perm.action, action):
                    if perm.effect == "deny":
                        return False

        # 2. 检查 Allow
        for role in roles:
            for perm in role.permissions:
                if self._match_resource(perm.resource, resource) and \
                   self._match_action(perm.action, action):
                    if perm.effect == "allow":
                        return True

        return False

    def _match_resource(self, pattern: str, resource: str) -> bool:
        """匹配资源"""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return resource.startswith(prefix)
        return pattern == resource

    def _match_action(self, pattern: str, action: str) -> bool:
        """匹配操作"""
        if pattern == "admin":
            return True  # admin 匹配所有操作
        return pattern == action


# 全局单例
_authz_service: Optional[AuthzService] = None


def get_authz_service(redis_client: Optional[Any] = None) -> AuthzService:
    """获取授权服务单例

    Args:
        redis_client: Redis 客户端

    Returns:
        授权服务实例
    """
    global _authz_service

    if _authz_service is None:
        _authz_service = AuthzService(redis_client)

    return _authz_service
