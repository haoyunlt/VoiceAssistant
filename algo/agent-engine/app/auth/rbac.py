"""
RBAC (Role-Based Access Control) for Python services
"""

from enum import Enum
from typing import Dict, List, Set


class Role(str, Enum):
    """User roles"""

    ADMIN = "admin"
    USER = "user"
    DEVELOPER = "developer"
    GUEST = "guest"


class Permission(str, Enum):
    """Permissions"""

    # User permissions
    READ_USER = "user:read"
    WRITE_USER = "user:write"
    DELETE_USER = "user:delete"

    # Chat permissions
    CHAT = "chat:use"
    CHAT_HISTORY = "chat:history"

    # Knowledge Graph permissions
    READ_KG = "kg:read"
    WRITE_KG = "kg:write"
    DELETE_KG = "kg:delete"

    # RAG permissions
    USE_RAG = "rag:use"
    MANAGE_RAG = "rag:manage"

    # Agent permissions
    USE_AGENT = "agent:use"
    MANAGE_AGENT = "agent:manage"

    # System permissions
    READ_METRICS = "system:metrics"
    MANAGE_SYSTEM = "system:manage"


class RBACManager:
    """RBAC manager"""

    def __init__(self):
        self.role_permissions: Dict[Role, Set[Permission]] = {}
        self._initialize_default_roles()

    def _initialize_default_roles(self):
        """Initialize default role permissions"""
        # Admin - Full access
        self.role_permissions[Role.ADMIN] = {
            Permission.READ_USER,
            Permission.WRITE_USER,
            Permission.DELETE_USER,
            Permission.CHAT,
            Permission.CHAT_HISTORY,
            Permission.READ_KG,
            Permission.WRITE_KG,
            Permission.DELETE_KG,
            Permission.USE_RAG,
            Permission.MANAGE_RAG,
            Permission.USE_AGENT,
            Permission.MANAGE_AGENT,
            Permission.READ_METRICS,
            Permission.MANAGE_SYSTEM,
        }

        # Developer - Development access
        self.role_permissions[Role.DEVELOPER] = {
            Permission.READ_USER,
            Permission.CHAT,
            Permission.CHAT_HISTORY,
            Permission.READ_KG,
            Permission.WRITE_KG,
            Permission.USE_RAG,
            Permission.MANAGE_RAG,
            Permission.USE_AGENT,
            Permission.MANAGE_AGENT,
            Permission.READ_METRICS,
        }

        # User - Standard user access
        self.role_permissions[Role.USER] = {
            Permission.READ_USER,
            Permission.CHAT,
            Permission.CHAT_HISTORY,
            Permission.READ_KG,
            Permission.USE_RAG,
            Permission.USE_AGENT,
        }

        # Guest - Limited access
        self.role_permissions[Role.GUEST] = {
            Permission.CHAT,
            Permission.READ_KG,
        }

    def has_permission(self, role: Role, permission: Permission) -> bool:
        """Check if a role has a specific permission"""
        return permission in self.role_permissions.get(role, set())

    def has_any_permission(
        self, role: Role, permissions: List[Permission]
    ) -> bool:
        """Check if a role has any of the specified permissions"""
        role_perms = self.role_permissions.get(role, set())
        return any(perm in role_perms for perm in permissions)

    def has_all_permissions(
        self, role: Role, permissions: List[Permission]
    ) -> bool:
        """Check if a role has all of the specified permissions"""
        role_perms = self.role_permissions.get(role, set())
        return all(perm in role_perms for perm in permissions)

    def check_user_permission(
        self, roles: List[str], permission: Permission
    ) -> bool:
        """Check if a user (with multiple roles) has a permission"""
        for role_str in roles:
            try:
                role = Role(role_str)
                if self.has_permission(role, permission):
                    return True
            except ValueError:
                continue
        return False

    def check_user_permissions(
        self, roles: List[str], permissions: List[Permission]
    ) -> bool:
        """Check if a user has all specified permissions"""
        for permission in permissions:
            if not self.check_user_permission(roles, permission):
                return False
        return True

    def add_permission_to_role(self, role: Role, permission: Permission):
        """Add a permission to a role"""
        if role not in self.role_permissions:
            self.role_permissions[role] = set()
        self.role_permissions[role].add(permission)

    def remove_permission_from_role(self, role: Role, permission: Permission):
        """Remove a permission from a role"""
        if role in self.role_permissions:
            self.role_permissions[role].discard(permission)

    def get_role_permissions(self, role: Role) -> List[Permission]:
        """Get all permissions for a role"""
        return list(self.role_permissions.get(role, set()))

    def validate_role(self, role: str) -> bool:
        """Validate if a role is valid"""
        try:
            Role(role)
            return True
        except ValueError:
            return False


# Global RBAC manager instance
_rbac_manager: RBACManager = None


def get_rbac_manager() -> RBACManager:
    """Get the global RBAC manager instance"""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager
