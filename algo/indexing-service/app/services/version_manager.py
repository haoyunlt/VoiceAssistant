"""文档版本管理服务

提供增量索引支持:
- 文档版本跟踪
- 内容哈希对比
- 变更检测
- 版本历史管理
"""

import hashlib
import json
import logging
import time

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentVersion(BaseModel):
    """文档版本模型"""

    document_id: str
    version: int
    content_hash: str
    metadata_hash: str
    chunk_count: int
    vector_count: int
    created_at: float
    updated_at: float
    tenant_id: str | None = None
    user_id: str | None = None
    status: str = "active"  # active, deleted, archived


class VersionChange(BaseModel):
    """版本变更模型"""

    change_type: str  # "created", "updated", "deleted", "unchanged"
    old_version: int | None = None
    new_version: int | None = None
    content_changed: bool = False
    metadata_changed: bool = False
    needs_reindex: bool = False


class VersionManager:
    """文档版本管理器"""

    def __init__(self, redis_client=None):
        """
        初始化版本管理器

        Args:
            redis_client: Redis客户端（用于存储版本信息）
        """
        self.redis = redis_client
        self.version_key_prefix = "doc_version:"
        self.history_key_prefix = "doc_history:"
        self.ttl_days = 365  # 版本信息保留1年

        logger.info("Version Manager initialized")

    def calculate_content_hash(self, content: str) -> str:
        """
        计算内容哈希

        Args:
            content: 文档内容

        Returns:
            SHA256哈希值
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def calculate_metadata_hash(self, metadata: dict) -> str:
        """
        计算元数据哈希

        Args:
            metadata: 元数据字典

        Returns:
            SHA256哈希值
        """
        # 排序键以确保一致性
        sorted_metadata = json.dumps(metadata, sort_keys=True)
        return hashlib.sha256(sorted_metadata.encode("utf-8")).hexdigest()

    async def get_current_version(
        self, document_id: str, tenant_id: str | None = None
    ) -> DocumentVersion | None:
        """
        获取文档当前版本

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            文档版本对象，不存在则返回None
        """
        if not self.redis:
            logger.warning("Redis not available, version tracking disabled")
            return None

        try:
            key = self._get_version_key(document_id, tenant_id)
            version_data = await self.redis.get(key)

            if version_data:
                return DocumentVersion(**json.loads(version_data))

            return None

        except Exception as e:
            logger.error(f"Failed to get current version for {document_id}: {e}")
            return None

    async def save_version(
        self,
        document_id: str,
        content_hash: str,
        metadata_hash: str,
        chunk_count: int,
        vector_count: int,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> DocumentVersion:
        """
        保存文档版本

        Args:
            document_id: 文档ID
            content_hash: 内容哈希
            metadata_hash: 元数据哈希
            chunk_count: 分块数量
            vector_count: 向量数量
            tenant_id: 租户ID
            user_id: 用户ID

        Returns:
            新的文档版本对象
        """
        if not self.redis:
            logger.warning("Redis not available, version not saved")
            # 返回临时版本对象
            return DocumentVersion(
                document_id=document_id,
                version=1,
                content_hash=content_hash,
                metadata_hash=metadata_hash,
                chunk_count=chunk_count,
                vector_count=vector_count,
                created_at=time.time(),
                updated_at=time.time(),
                tenant_id=tenant_id,
                user_id=user_id,
            )

        try:
            # 获取当前版本
            current_version = await self.get_current_version(document_id, tenant_id)

            # 计算新版本号
            new_version_number = (current_version.version + 1) if current_version else 1

            # 创建新版本对象
            new_version = DocumentVersion(
                document_id=document_id,
                version=new_version_number,
                content_hash=content_hash,
                metadata_hash=metadata_hash,
                chunk_count=chunk_count,
                vector_count=vector_count,
                created_at=current_version.created_at if current_version else time.time(),
                updated_at=time.time(),
                tenant_id=tenant_id,
                user_id=user_id,
                status="active",
            )

            # 保存到Redis
            key = self._get_version_key(document_id, tenant_id)
            await self.redis.setex(
                key,
                self.ttl_days * 86400,  # 转换为秒
                json.dumps(new_version.dict()),
            )

            # 保存到历史记录
            await self._save_to_history(new_version, tenant_id)

            logger.info(f"Saved version {new_version_number} for document {document_id}")

            return new_version

        except Exception as e:
            logger.error(f"Failed to save version for {document_id}: {e}")
            raise

    async def detect_changes(
        self,
        document_id: str,
        new_content_hash: str,
        new_metadata_hash: str,
        tenant_id: str | None = None,
    ) -> VersionChange:
        """
        检测文档变更

        Args:
            document_id: 文档ID
            new_content_hash: 新内容哈希
            new_metadata_hash: 新元数据哈希
            tenant_id: 租户ID

        Returns:
            版本变更对象
        """
        # 获取当前版本
        current_version = await self.get_current_version(document_id, tenant_id)

        if not current_version:
            # 新文档
            return VersionChange(
                change_type="created",
                new_version=1,
                content_changed=True,
                metadata_changed=True,
                needs_reindex=True,
            )

        # 检查内容是否变化
        content_changed = new_content_hash != current_version.content_hash
        metadata_changed = new_metadata_hash != current_version.metadata_hash

        if not content_changed and not metadata_changed:
            # 无变更
            return VersionChange(
                change_type="unchanged",
                old_version=current_version.version,
                new_version=current_version.version,
                content_changed=False,
                metadata_changed=False,
                needs_reindex=False,
            )

        # 有变更
        return VersionChange(
            change_type="updated",
            old_version=current_version.version,
            new_version=current_version.version + 1,
            content_changed=content_changed,
            metadata_changed=metadata_changed,
            needs_reindex=content_changed,  # 只有内容变化时才需要重新索引
        )

    async def mark_deleted(self, document_id: str, tenant_id: str | None = None) -> bool:
        """
        标记文档为已删除

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            是否成功
        """
        if not self.redis:
            return False

        try:
            current_version = await self.get_current_version(document_id, tenant_id)

            if not current_version:
                logger.warning(f"Document {document_id} not found, cannot mark as deleted")
                return False

            # 更新状态为deleted
            current_version.status = "deleted"
            current_version.updated_at = time.time()

            # 保存更新
            key = self._get_version_key(document_id, tenant_id)
            await self.redis.setex(key, self.ttl_days * 86400, json.dumps(current_version.dict()))

            logger.info(f"Marked document {document_id} as deleted")
            return True

        except Exception as e:
            logger.error(f"Failed to mark document {document_id} as deleted: {e}")
            return False

    async def get_version_history(
        self, document_id: str, tenant_id: str | None = None, limit: int = 10
    ) -> list[DocumentVersion]:
        """
        获取文档版本历史

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            limit: 返回数量限制

        Returns:
            版本历史列表（从新到旧）
        """
        if not self.redis:
            return []

        try:
            history_key = self._get_history_key(document_id, tenant_id)

            # 从Redis列表获取历史记录
            history_data = await self.redis.lrange(history_key, 0, limit - 1)

            versions = []
            for data in history_data:
                versions.append(DocumentVersion(**json.loads(data)))

            return versions

        except Exception as e:
            logger.error(f"Failed to get version history for {document_id}: {e}")
            return []

    async def _save_to_history(self, version: DocumentVersion, tenant_id: str | None = None):
        """保存版本到历史记录"""
        try:
            history_key = self._get_history_key(version.document_id, tenant_id)

            # 添加到列表头部（最新的在前）
            await self.redis.lpush(history_key, json.dumps(version.dict()))

            # 限制历史记录数量（保留最近100个版本）
            await self.redis.ltrim(history_key, 0, 99)

            # 设置过期时间
            await self.redis.expire(history_key, self.ttl_days * 86400)

        except Exception as e:
            logger.warning(f"Failed to save to history: {e}")

    def _get_version_key(self, document_id: str, tenant_id: str | None = None) -> str:
        """生成版本键"""
        if tenant_id:
            return f"{self.version_key_prefix}{tenant_id}:{document_id}"
        return f"{self.version_key_prefix}{document_id}"

    def _get_history_key(self, document_id: str, tenant_id: str | None = None) -> str:
        """生成历史记录键"""
        if tenant_id:
            return f"{self.history_key_prefix}{tenant_id}:{document_id}"
        return f"{self.history_key_prefix}{document_id}"

    async def get_stats(self) -> dict:
        """获取版本管理统计信息"""
        if not self.redis:
            return {"enabled": False, "message": "Redis not available"}

        try:
            # 获取所有版本键的数量
            version_keys = await self.redis.keys(f"{self.version_key_prefix}*")

            return {
                "enabled": True,
                "total_documents": len(version_keys),
                "ttl_days": self.ttl_days,
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"enabled": True, "error": str(e)}

    async def cleanup_old_versions(self, days_threshold: int = 365):
        """
        清理旧版本（超过阈值的版本）

        Args:
            days_threshold: 天数阈值
        """
        if not self.redis:
            logger.warning("Redis not available, cleanup skipped")
            return

        try:
            threshold_time = time.time() - (days_threshold * 86400)
            cleaned_count = 0

            # 获取所有版本键
            version_keys = await self.redis.keys(f"{self.version_key_prefix}*")

            for key in version_keys:
                version_data = await self.redis.get(key)
                if version_data:
                    version = DocumentVersion(**json.loads(version_data))

                    # 如果更新时间超过阈值且状态为deleted或archived
                    if version.updated_at < threshold_time and version.status in [
                        "deleted",
                        "archived",
                    ]:
                        await self.redis.delete(key)
                        cleaned_count += 1

            logger.info(f"Cleaned up {cleaned_count} old versions")

        except Exception as e:
            logger.error(f"Failed to cleanup old versions: {e}")


async def get_version_manager(redis_client=None) -> VersionManager:
    """获取版本管理器单例"""
    return VersionManager(redis_client)
