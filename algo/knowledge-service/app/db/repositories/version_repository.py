"""
Version Repository

版本数据访问层
"""

import logging

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VersionModel
from app.services.version_manager import KnowledgeBaseVersion, VersionSnapshot

logger = logging.getLogger(__name__)


class VersionRepository:
    """版本仓库"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, version: KnowledgeBaseVersion) -> KnowledgeBaseVersion:
        """创建版本

        Args:
            version: 版本对象

        Returns:
            创建的版本
        """
        model = VersionModel(
            id=version.id,
            knowledge_base_id=version.knowledge_base_id,
            version=version.version,
            snapshot=version.snapshot.to_dict(),
            description=version.description,
            created_by=version.created_by,
            tenant_id=version.tenant_id,
            created_at=version.created_at,
        )

        self.session.add(model)
        await self.session.flush()

        logger.info(f"Created version: {version.id}")
        return version

    async def get_by_id(self, version_id: str) -> KnowledgeBaseVersion | None:
        """根据 ID 获取版本

        Args:
            version_id: 版本 ID

        Returns:
            版本对象或 None
        """
        result = await self.session.execute(
            select(VersionModel).where(VersionModel.id == version_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def list_by_knowledge_base(
        self, knowledge_base_id: str, offset: int = 0, limit: int = 10
    ) -> tuple[list[KnowledgeBaseVersion], int]:
        """列出知识库的版本

        Args:
            knowledge_base_id: 知识库 ID
            offset: 偏移量
            limit: 数量限制

        Returns:
            (版本列表, 总数)
        """
        # 查询总数
        count_result = await self.session.execute(
            select(VersionModel).where(VersionModel.knowledge_base_id == knowledge_base_id)
        )
        total = len(count_result.all())

        # 查询数据
        result = await self.session.execute(
            select(VersionModel)
            .where(VersionModel.knowledge_base_id == knowledge_base_id)
            .order_by(desc(VersionModel.version))
            .offset(offset)
            .limit(limit)
        )
        models = result.scalars().all()

        versions = [self._model_to_entity(model) for model in models]

        return versions, total

    async def get_latest_version(self, knowledge_base_id: str) -> KnowledgeBaseVersion | None:
        """获取最新版本

        Args:
            knowledge_base_id: 知识库 ID

        Returns:
            最新版本或 None
        """
        result = await self.session.execute(
            select(VersionModel)
            .where(VersionModel.knowledge_base_id == knowledge_base_id)
            .order_by(desc(VersionModel.version))
            .limit(1)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def delete(self, version_id: str) -> bool:
        """删除版本

        Args:
            version_id: 版本 ID

        Returns:
            是否成功
        """
        result = await self.session.execute(
            select(VersionModel).where(VersionModel.id == version_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self.session.delete(model)
        await self.session.flush()

        logger.info(f"Deleted version: {version_id}")
        return True

    def _model_to_entity(self, model: VersionModel) -> KnowledgeBaseVersion:
        """将模型转换为实体

        Args:
            model: 数据库模型

        Returns:
            版本实体
        """
        snapshot = VersionSnapshot(**model.snapshot)

        return KnowledgeBaseVersion(
            id=model.id,
            knowledge_base_id=model.knowledge_base_id,
            version=model.version,
            snapshot=snapshot,
            description=model.description,
            created_by=model.created_by,
            tenant_id=model.tenant_id,
            created_at=model.created_at,
        )
