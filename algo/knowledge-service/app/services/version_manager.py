"""
Version Management Service

版本管理服务，负责知识库的版本控制和回滚
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class VersionSnapshot:
    """版本快照"""

    def __init__(
        self,
        document_count: int = 0,
        chunk_count: int = 0,
        entity_count: int = 0,
        relation_count: int = 0,
        vector_index_hash: str = "",
        graph_snapshot_id: str = "",
        metadata: Optional[Dict[str, str]] = None,
        created_at: Optional[datetime] = None
    ):
        self.document_count = document_count
        self.chunk_count = chunk_count
        self.entity_count = entity_count
        self.relation_count = relation_count
        self.vector_index_hash = vector_index_hash
        self.graph_snapshot_id = graph_snapshot_id
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "vector_index_hash": self.vector_index_hash,
            "graph_snapshot_id": self.graph_snapshot_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class KnowledgeBaseVersion:
    """知识库版本"""

    def __init__(
        self,
        id: str,
        knowledge_base_id: str,
        version: int,
        snapshot: VersionSnapshot,
        description: str,
        created_by: str,
        tenant_id: str,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.knowledge_base_id = knowledge_base_id
        self.version = version
        self.snapshot = snapshot
        self.description = description
        self.created_by = created_by
        self.tenant_id = tenant_id
        self.created_at = created_at or datetime.utcnow()

    @classmethod
    def create(
        cls,
        knowledge_base_id: str,
        version: int,
        created_by: str,
        tenant_id: str,
        description: str,
        snapshot: VersionSnapshot
    ) -> "KnowledgeBaseVersion":
        """创建新版本"""
        version_id = f"ver_{uuid4()}"
        return cls(
            id=version_id,
            knowledge_base_id=knowledge_base_id,
            version=version,
            snapshot=snapshot,
            description=description,
            created_by=created_by,
            tenant_id=tenant_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "version": self.version,
            "snapshot": self.snapshot.to_dict(),
            "description": self.description,
            "created_by": self.created_by,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat()
        }


class VersionManager:
    """版本管理器"""

    def __init__(
        self,
        neo4j_client: Any,  # Neo4j 客户端
        # indexing_client: Optional[Any] = None,  # 索引服务客户端（可选）
    ):
        """初始化版本管理器

        Args:
            neo4j_client: Neo4j 客户端
        """
        self.neo4j = neo4j_client
        # self.indexing_client = indexing_client
        self._versions_cache: Dict[str, List[KnowledgeBaseVersion]] = {}

    async def create_version(
        self,
        knowledge_base_id: str,
        created_by: str,
        tenant_id: str,
        description: str = ""
    ) -> KnowledgeBaseVersion:
        """创建版本快照

        Args:
            knowledge_base_id: 知识库 ID
            created_by: 创建者 ID
            tenant_id: 租户 ID
            description: 版本描述

        Returns:
            版本对象
        """
        logger.info(f"Creating version snapshot for knowledge base: {knowledge_base_id}")

        # 获取下一个版本号
        next_version = await self._get_next_version(knowledge_base_id)

        # 捕获当前快照
        snapshot = await self._capture_snapshot(knowledge_base_id)

        # 创建版本对象
        version = KnowledgeBaseVersion.create(
            knowledge_base_id=knowledge_base_id,
            version=next_version,
            created_by=created_by,
            tenant_id=tenant_id,
            description=description,
            snapshot=snapshot
        )

        # 保存版本（实际应保存到数据库）
        # await self._save_version(version)

        # 更新缓存
        if knowledge_base_id not in self._versions_cache:
            self._versions_cache[knowledge_base_id] = []
        self._versions_cache[knowledge_base_id].append(version)

        logger.info(
            f"Version {version.version} created for KB {knowledge_base_id}: "
            f"docs={snapshot.document_count}, chunks={snapshot.chunk_count}, "
            f"entities={snapshot.entity_count}"
        )

        return version

    async def get_versions(
        self,
        knowledge_base_id: str,
        offset: int = 0,
        limit: int = 10
    ) -> List[KnowledgeBaseVersion]:
        """获取知识库的版本列表

        Args:
            knowledge_base_id: 知识库 ID
            offset: 偏移量
            limit: 数量限制

        Returns:
            版本列表
        """
        # 从缓存获取（实际应从数据库获取）
        versions = self._versions_cache.get(knowledge_base_id, [])
        return sorted(versions, key=lambda v: v.version, reverse=True)[offset:offset+limit]

    async def get_version(self, version_id: str) -> Optional[KnowledgeBaseVersion]:
        """获取指定版本

        Args:
            version_id: 版本 ID

        Returns:
            版本对象
        """
        for versions in self._versions_cache.values():
            for version in versions:
                if version.id == version_id:
                    return version
        return None

    async def rollback_to_version(
        self,
        version_id: str,
        initiated_by: str
    ) -> bool:
        """回滚到指定版本

        Args:
            version_id: 版本 ID
            initiated_by: 操作者 ID

        Returns:
            是否成功
        """
        logger.info(f"Rolling back to version: {version_id}")

        # 获取目标版本
        target_version = await self.get_version(version_id)
        if not target_version:
            logger.error(f"Version not found: {version_id}")
            return False

        # 1. 创建当前版本快照（作为保留点）
        logger.info("Creating savepoint before rollback...")
        await self.create_version(
            knowledge_base_id=target_version.knowledge_base_id,
            created_by=initiated_by,
            tenant_id=target_version.tenant_id,
            description=f"Auto-savepoint before rollback to version {target_version.version}"
        )

        # 2. 恢复向量索引（调用 indexing-service）
        # if self.indexing_client:
        #     logger.info("Restoring vector index...")
        #     await self.indexing_client.restore_index(
        #         target_version.snapshot.vector_index_hash
        #     )

        # 3. 恢复知识图谱
        logger.info("Restoring knowledge graph...")
        await self._restore_graph_snapshot(target_version.snapshot.graph_snapshot_id)

        # 4. 更新知识库元数据
        logger.info("Updating knowledge base metadata...")
        # await self._update_kb_metadata(target_version)

        logger.info(f"Rollback completed to version {target_version.version}")
        return True

    async def delete_version(self, version_id: str) -> bool:
        """删除版本

        Args:
            version_id: 版本 ID

        Returns:
            是否成功
        """
        for kb_id, versions in self._versions_cache.items():
            for i, version in enumerate(versions):
                if version.id == version_id:
                    del versions[i]
                    logger.info(f"Deleted version: {version_id}")
                    return True
        return False

    async def _get_next_version(self, knowledge_base_id: str) -> int:
        """获取下一个版本号"""
        versions = self._versions_cache.get(knowledge_base_id, [])
        if not versions:
            return 1
        return max(v.version for v in versions) + 1

    async def _capture_snapshot(self, knowledge_base_id: str) -> VersionSnapshot:
        """捕获当前状态快照"""
        # 统计实体和关系数量
        query = """
        MATCH (e:Entity {knowledge_base_id: $kb_id})
        WITH count(e) as entity_count
        MATCH (e1:Entity {knowledge_base_id: $kb_id})-[r]-(e2:Entity {knowledge_base_id: $kb_id})
        RETURN entity_count, count(DISTINCT r) as relation_count
        """

        result = await self.neo4j.execute_query(query, {"kb_id": knowledge_base_id})

        entity_count = 0
        relation_count = 0
        if result:
            entity_count = result[0].get("entity_count", 0)
            relation_count = result[0].get("relation_count", 0)

        # 导出图谱快照
        graph_snapshot_id = await self._export_graph_snapshot(knowledge_base_id)

        return VersionSnapshot(
            document_count=0,  # TODO: 从文档管理服务获取
            chunk_count=0,     # TODO: 从文档管理服务获取
            entity_count=entity_count,
            relation_count=relation_count,
            vector_index_hash="",  # TODO: 从索引服务获取
            graph_snapshot_id=graph_snapshot_id,
            metadata={
                "captured_by": "version_manager"
            }
        )

    async def _export_graph_snapshot(self, knowledge_base_id: str) -> str:
        """导出图谱快照

        Args:
            knowledge_base_id: 知识库 ID

        Returns:
            快照 ID
        """
        snapshot_id = f"snapshot_{uuid4()}"

        # 导出所有节点和关系
        query = """
        MATCH (e:Entity {knowledge_base_id: $kb_id})
        OPTIONAL MATCH (e)-[r]-(e2:Entity {knowledge_base_id: $kb_id})
        RETURN e, r, e2
        """

        result = await self.neo4j.execute_query(query, {"kb_id": knowledge_base_id})

        # TODO: 将结果序列化并存储
        logger.info(f"Exported graph snapshot: {snapshot_id}")

        return snapshot_id

    async def _restore_graph_snapshot(self, snapshot_id: str) -> None:
        """恢复图谱快照

        Args:
            snapshot_id: 快照 ID
        """
        # TODO: 从存储中读取快照并恢复到 Neo4j
        logger.info(f"Restoring graph snapshot: {snapshot_id}")


# 全局单例
_version_manager: Optional[VersionManager] = None


def get_version_manager(neo4j_client: Optional[Any] = None) -> VersionManager:
    """获取版本管理器单例

    Args:
        neo4j_client: Neo4j 客户端

    Returns:
        版本管理器实例
    """
    global _version_manager

    if _version_manager is None:
        if neo4j_client is None:
            raise ValueError("Version manager not initialized. Provide Neo4j client.")
        _version_manager = VersionManager(neo4j_client)

    return _version_manager
