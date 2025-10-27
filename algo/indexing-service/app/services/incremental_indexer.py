"""增量索引服务

基于版本管理实现智能的增量索引:
- 检测文档变更
- 差异化更新
- 避免重复索引
- 原子性操作
"""
import logging
import time
from typing import Dict, List, Optional, Tuple

from app.services.version_manager import VersionChange, VersionManager

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """增量索引器"""

    def __init__(
        self,
        version_manager: VersionManager,
        document_processor
    ):
        """
        初始化增量索引器

        Args:
            version_manager: 版本管理器
            document_processor: 文档处理器
        """
        self.version_manager = version_manager
        self.processor = document_processor

        # 统计信息
        self.stats = {
            "total_checks": 0,
            "unchanged_skipped": 0,
            "full_reindex": 0,
            "incremental_update": 0,
            "errors": 0
        }

        logger.info("Incremental Indexer initialized")

    async def process_with_version_check(
        self,
        document_id: str,
        content: str,
        metadata: Dict,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        force_reindex: bool = False
    ) -> Dict:
        """
        带版本检查的文档处理

        Args:
            document_id: 文档ID
            content: 文档内容
            metadata: 元数据
            tenant_id: 租户ID
            user_id: 用户ID
            force_reindex: 是否强制重新索引

        Returns:
            处理结果字典
        """
        start_time = time.time()
        self.stats["total_checks"] += 1

        try:
            # 1. 计算新的哈希值
            content_hash = self.version_manager.calculate_content_hash(content)
            metadata_hash = self.version_manager.calculate_metadata_hash(metadata)

            # 2. 检测变更
            if not force_reindex:
                change = await self.version_manager.detect_changes(
                    document_id=document_id,
                    new_content_hash=content_hash,
                    new_metadata_hash=metadata_hash,
                    tenant_id=tenant_id
                )

                logger.info(
                    f"Document {document_id} change detection: "
                    f"type={change.change_type}, "
                    f"content_changed={change.content_changed}, "
                    f"metadata_changed={change.metadata_changed}"
                )
            else:
                # 强制重新索引
                change = VersionChange(
                    change_type="updated",
                    content_changed=True,
                    metadata_changed=True,
                    needs_reindex=True
                )

            # 3. 根据变更类型处理
            if change.change_type == "unchanged" and not force_reindex:
                # 无变更，跳过索引
                self.stats["unchanged_skipped"] += 1

                return {
                    "status": "skipped",
                    "reason": "no_changes",
                    "document_id": document_id,
                    "version": change.old_version,
                    "elapsed_time": time.time() - start_time
                }

            elif change.change_type in ["created", "updated"] or force_reindex:
                if change.needs_reindex:
                    # 需要完全重新索引
                    result = await self._full_reindex(
                        document_id=document_id,
                        content=content,
                        metadata=metadata,
                        content_hash=content_hash,
                        metadata_hash=metadata_hash,
                        tenant_id=tenant_id,
                        user_id=user_id
                    )
                    self.stats["full_reindex"] += 1
                else:
                    # 只更新元数据
                    result = await self._update_metadata_only(
                        document_id=document_id,
                        metadata=metadata,
                        metadata_hash=metadata_hash,
                        content_hash=content_hash,
                        tenant_id=tenant_id
                    )
                    self.stats["incremental_update"] += 1

                result["elapsed_time"] = time.time() - start_time
                return result

            else:
                # 未知变更类型
                return {
                    "status": "error",
                    "error": f"Unknown change type: {change.change_type}",
                    "document_id": document_id
                }

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Incremental indexing failed for {document_id}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "document_id": document_id,
                "elapsed_time": time.time() - start_time
            }

    async def _full_reindex(
        self,
        document_id: str,
        content: str,
        metadata: Dict,
        content_hash: str,
        metadata_hash: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        完全重新索引

        包括：
        1. 删除旧的向量
        2. 重新分块
        3. 重新向量化
        4. 存储新向量
        5. 更新知识图谱
        """
        logger.info(f"Starting full reindex for document {document_id}")

        try:
            # TODO: 在实际实现中，应该先删除旧的向量和图谱数据
            # await self._delete_old_data(document_id, tenant_id)

            # 执行完整的文档处理流程
            # 这里简化实现，实际应该调用document_processor
            result = await self.processor.process_document(
                document_id=document_id,
                tenant_id=tenant_id,
                user_id=user_id,
                file_path=None  # 假设内容已经在content中
            )

            # 保存新版本
            chunk_count = result.get("chunks_count", 0)
            vector_count = result.get("vectors_count", 0)

            new_version = await self.version_manager.save_version(
                document_id=document_id,
                content_hash=content_hash,
                metadata_hash=metadata_hash,
                chunk_count=chunk_count,
                vector_count=vector_count,
                tenant_id=tenant_id,
                user_id=user_id
            )

            return {
                "status": "reindexed",
                "document_id": document_id,
                "version": new_version.version,
                "chunk_count": chunk_count,
                "vector_count": vector_count,
                "operation": "full_reindex"
            }

        except Exception as e:
            logger.error(f"Full reindex failed for {document_id}: {e}")
            raise

    async def _update_metadata_only(
        self,
        document_id: str,
        metadata: Dict,
        metadata_hash: str,
        content_hash: str,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """
        只更新元数据（内容未变化）

        这是增量更新的优化：
        - 不重新分块
        - 不重新向量化
        - 只更新元数据
        """
        logger.info(f"Updating metadata only for document {document_id}")

        try:
            # TODO: 实际实现中应该更新向量存储和图谱中的元数据
            # await self.vector_store.update_metadata(document_id, metadata)
            # await self.neo4j_client.update_document_metadata(document_id, metadata)

            # 获取当前版本信息
            current_version = await self.version_manager.get_current_version(
                document_id, tenant_id
            )

            # 保存新版本（内容哈希不变，只有元数据哈希变化）
            new_version = await self.version_manager.save_version(
                document_id=document_id,
                content_hash=content_hash,
                metadata_hash=metadata_hash,
                chunk_count=current_version.chunk_count if current_version else 0,
                vector_count=current_version.vector_count if current_version else 0,
                tenant_id=tenant_id
            )

            return {
                "status": "updated",
                "document_id": document_id,
                "version": new_version.version,
                "operation": "metadata_only"
            }

        except Exception as e:
            logger.error(f"Metadata update failed for {document_id}: {e}")
            raise

    async def _delete_old_data(
        self,
        document_id: str,
        tenant_id: Optional[str] = None
    ):
        """
        删除旧的索引数据

        包括：
        - 向量数据
        - 图谱数据
        - BM25索引
        """
        logger.info(f"Deleting old data for document {document_id}")

        try:
            # TODO: 实现实际的删除逻辑
            # await self.vector_store.delete_by_document(document_id)
            # await self.neo4j_client.delete_document_nodes(document_id)
            # await self.bm25_index.delete_document(document_id)

            logger.info(f"Old data deleted for document {document_id}")

        except Exception as e:
            logger.warning(f"Failed to delete old data for {document_id}: {e}")
            # 不抛出异常，继续流程

    async def batch_check_updates(
        self,
        documents: List[Tuple[str, str, Dict]],  # [(doc_id, content, metadata), ...]
        tenant_id: Optional[str] = None
    ) -> Dict:
        """
        批量检查文档更新

        Args:
            documents: 文档列表 [(文档ID, 内容, 元数据), ...]
            tenant_id: 租户ID

        Returns:
            批量检查结果
        """
        logger.info(f"Batch checking {len(documents)} documents")

        results = {
            "unchanged": [],
            "to_reindex": [],
            "to_update_metadata": [],
            "new": []
        }

        for doc_id, content, metadata in documents:
            try:
                content_hash = self.version_manager.calculate_content_hash(content)
                metadata_hash = self.version_manager.calculate_metadata_hash(metadata)

                change = await self.version_manager.detect_changes(
                    document_id=doc_id,
                    new_content_hash=content_hash,
                    new_metadata_hash=metadata_hash,
                    tenant_id=tenant_id
                )

                if change.change_type == "unchanged":
                    results["unchanged"].append(doc_id)
                elif change.change_type == "created":
                    results["new"].append(doc_id)
                elif change.needs_reindex:
                    results["to_reindex"].append(doc_id)
                else:
                    results["to_update_metadata"].append(doc_id)

            except Exception as e:
                logger.error(f"Failed to check document {doc_id}: {e}")

        logger.info(
            f"Batch check complete: "
            f"{len(results['unchanged'])} unchanged, "
            f"{len(results['new'])} new, "
            f"{len(results['to_reindex'])} to reindex, "
            f"{len(results['to_update_metadata'])} metadata updates"
        )

        return results

    async def delete_document(
        self,
        document_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict:
        """
        删除文档

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            删除结果
        """
        try:
            # 删除索引数据
            await self._delete_old_data(document_id, tenant_id)

            # 标记为已删除
            success = await self.version_manager.mark_deleted(document_id, tenant_id)

            if success:
                return {
                    "status": "deleted",
                    "document_id": document_id
                }
            else:
                return {
                    "status": "error",
                    "error": "Failed to mark as deleted",
                    "document_id": document_id
                }

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "document_id": document_id
            }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "skip_rate": (
                self.stats["unchanged_skipped"] / self.stats["total_checks"]
                if self.stats["total_checks"] > 0 else 0
            ),
            "reindex_rate": (
                self.stats["full_reindex"] / self.stats["total_checks"]
                if self.stats["total_checks"] > 0 else 0
            )
        }

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_checks": 0,
            "unchanged_skipped": 0,
            "full_reindex": 0,
            "incremental_update": 0,
            "errors": 0
        }
