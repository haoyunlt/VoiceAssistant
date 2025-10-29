"""
Authorization Repository

权限数据访问层
"""

import logging
from typing import List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLogModel, RoleModel, UserRoleModel
from app.services.authz_service import AuditLog, Permission, Role, UserRole

logger = logging.getLogger(__name__)


class AuthzRepository:
    """授权仓库"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========== Role Methods ==========

    async def create_role(self, role: Role) -> Role:
        """创建角色

        Args:
            role: 角色对象

        Returns:
            创建的角色
        """
        model = RoleModel(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=[p.to_dict() for p in role.permissions],
            tenant_id=role.tenant_id,
            created_at=role.created_at,
            updated_at=role.updated_at
        )

        self.session.add(model)
        await self.session.flush()

        logger.info(f"Created role: {role.id}")
        return role

    async def get_role_by_id(self, role_id: str) -> Optional[Role]:
        """根据 ID 获取角色

        Args:
            role_id: 角色 ID

        Returns:
            角色对象或 None
        """
        result = await self.session.execute(
            select(RoleModel).where(RoleModel.id == role_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._role_model_to_entity(model)

    async def get_role_by_name(self, name: str, tenant_id: str) -> Optional[Role]:
        """根据名称获取角色

        Args:
            name: 角色名称
            tenant_id: 租户 ID

        Returns:
            角色对象或 None
        """
        result = await self.session.execute(
            select(RoleModel).where(
                and_(
                    RoleModel.name == name,
                    RoleModel.tenant_id == tenant_id
                )
            )
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._role_model_to_entity(model)

    # ========== UserRole Methods ==========

    async def grant_role(self, user_role: UserRole) -> UserRole:
        """授予角色

        Args:
            user_role: 用户角色关联

        Returns:
            用户角色关联
        """
        model = UserRoleModel(
            id=user_role.id,
            user_id=user_role.user_id,
            role_id=user_role.role_id,
            tenant_id=user_role.tenant_id,
            resource=user_role.resource,
            created_at=user_role.created_at,
            expires_at=user_role.expires_at
        )

        self.session.add(model)
        await self.session.flush()

        logger.info(f"Granted role {user_role.role_id} to user {user_role.user_id}")
        return user_role

    async def revoke_role(self, user_id: str, role_id: str) -> bool:
        """撤销角色

        Args:
            user_id: 用户 ID
            role_id: 角色 ID

        Returns:
            是否成功
        """
        result = await self.session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id == role_id
                )
            )
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self.session.delete(model)
        await self.session.flush()

        logger.info(f"Revoked role {role_id} from user {user_id}")
        return True

    async def get_user_roles(self, user_id: str, tenant_id: str) -> List[Role]:
        """获取用户的所有角色

        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID

        Returns:
            角色列表
        """
        result = await self.session.execute(
            select(UserRoleModel).where(
                and_(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.tenant_id == tenant_id
                )
            )
        )
        user_role_models = result.scalars().all()

        # 获取所有角色
        roles = []
        for ur_model in user_role_models:
            role = await self.get_role_by_id(ur_model.role_id)
            if role:
                roles.append(role)

        return roles

    # ========== AuditLog Methods ==========

    async def create_audit_log(self, audit_log: AuditLog) -> AuditLog:
        """创建审计日志

        Args:
            audit_log: 审计日志对象

        Returns:
            创建的审计日志
        """
        model = AuditLogModel(
            id=audit_log.id,
            tenant_id=audit_log.tenant_id,
            user_id=audit_log.user_id,
            action=audit_log.action,
            resource=audit_log.resource,
            details=audit_log.details,
            ip=audit_log.ip,
            user_agent=audit_log.user_agent,
            status=audit_log.status,
            error=audit_log.error,
            created_at=audit_log.created_at
        )

        self.session.add(model)
        await self.session.flush()

        return audit_log

    async def list_audit_logs(
        self,
        tenant_id: str,
        offset: int = 0,
        limit: int = 100,
        user_id: Optional[str] = None,
        action: Optional[str] = None
    ) -> tuple[List[AuditLog], int]:
        """列出审计日志

        Args:
            tenant_id: 租户 ID
            offset: 偏移量
            limit: 数量限制
            user_id: 用户 ID（可选）
            action: 操作（可选）

        Returns:
            (审计日志列表, 总数)
        """
        # 构建条件
        conditions = [AuditLogModel.tenant_id == tenant_id]

        if user_id:
            conditions.append(AuditLogModel.user_id == user_id)
        if action:
            conditions.append(AuditLogModel.action == action)

        # 查询总数
        count_result = await self.session.execute(
            select(AuditLogModel).where(and_(*conditions))
        )
        total = len(count_result.all())

        # 查询数据
        result = await self.session.execute(
            select(AuditLogModel)
            .where(and_(*conditions))
            .order_by(desc(AuditLogModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        models = result.scalars().all()

        logs = [self._audit_log_model_to_entity(model) for model in models]

        return logs, total

    def _role_model_to_entity(self, model: RoleModel) -> Role:
        """将模型转换为实体

        Args:
            model: 数据库模型

        Returns:
            角色实体
        """
        permissions = [Permission(**p) for p in model.permissions]

        return Role(
            id=model.id,
            name=model.name,
            description=model.description,
            permissions=permissions,
            tenant_id=model.tenant_id,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _audit_log_model_to_entity(self, model: AuditLogModel) -> AuditLog:
        """将模型转换为实体

        Args:
            model: 数据库模型

        Returns:
            审计日志实体
        """
        return AuditLog(
            id=model.id,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            action=model.action,
            resource=model.resource or "",
            details=model.details or "",
            ip=model.ip or "",
            user_agent=model.user_agent or "",
            status=model.status,
            error=model.error or "",
            created_at=model.created_at
        )
