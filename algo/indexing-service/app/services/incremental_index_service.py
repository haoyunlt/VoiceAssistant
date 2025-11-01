"""
增量索引服务
实现文档版本管理、差异检测和原子更新
"""

import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)


class IncrementalIndexService:
    """增量索引服务"""

    def __init__(self, redis_client, version_ttl: int = 604800):
        """
        初始化增量索引服务

        Args:
            redis_client: Redis客户端
            version_ttl: 版本信息TTL（秒，默认7天）
        """
        self.redis = redis_client
        self.version_ttl = version_ttl
        self.version_key_prefix = "doc_version:"
        self.hash_key_prefix = "doc_hash:"

        logger.info(f"IncrementalIndexService initialized with TTL={version_ttl}s")

    async def compute_content_hash(self, content: str) -> str:
        """
        计算内容哈希

        Args:
            content: 文档内容

        Returns:
            SHA256哈希值
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get_document_version(self, document_id: str) -> dict | None:
        """
        获取文档版本信息

        Args:
            document_id: 文档ID

        Returns:
            版本信息字典，如果不存在返回None
        """
        try:
            version_key = f"{self.version_key_prefix}{document_id}"
            version_data = await self.redis.get(version_key)

            if version_data:
                return json.loads(version_data)

            return None

        except Exception as e:
            logger.error(f"Failed to get document version: {e}")
            return None

    async def save_document_version(
        self,
        document_id: str,
        content_hash: str,
        chunk_hashes: list[str],
        metadata: dict | None = None,
    ) -> bool:
        """
        保存文档版本信息

        Args:
            document_id: 文档ID
            content_hash: 内容哈希
            chunk_hashes: 分块哈希列表
            metadata: 元数据

        Returns:
            是否保存成功
        """
        try:
            version_info = {
                "document_id": document_id,
                "content_hash": content_hash,
                "chunk_hashes": chunk_hashes,
                "chunk_count": len(chunk_hashes),
                "metadata": metadata or {},
                "indexed_at": time.time(),
                "version": int(time.time() * 1000),  # 使用时间戳作为版本号
            }

            version_key = f"{self.version_key_prefix}{document_id}"
            await self.redis.setex(version_key, self.version_ttl, json.dumps(version_info))

            # 同时保存哈希到文档ID的映射
            hash_key = f"{self.hash_key_prefix}{content_hash}"
            await self.redis.setex(hash_key, self.version_ttl, document_id)

            logger.info(f"Saved version for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save document version: {e}")
            return False

    async def detect_changes(
        self, document_id: str, new_content: str, new_chunks: list[str]
    ) -> dict:
        """
        检测文档变更

        Args:
            document_id: 文档ID
            new_content: 新内容
            new_chunks: 新分块列表

        Returns:
            变更检测结果
        """
        # 计算新内容哈希
        new_content_hash = await self.compute_content_hash(new_content)

        # 计算新分块哈希
        new_chunk_hashes = [await self.compute_content_hash(chunk) for chunk in new_chunks]

        # 获取旧版本
        old_version = await self.get_document_version(document_id)

        # 如果没有旧版本，视为新文档
        if not old_version:
            return {
                "is_new": True,
                "has_changes": True,
                "content_changed": True,
                "new_chunks": list(range(len(new_chunks))),
                "updated_chunks": [],
                "deleted_chunks": [],
                "unchanged_chunks": [],
                "change_summary": {
                    "total_chunks": len(new_chunks),
                    "new_chunks_count": len(new_chunks),
                    "changed_chunks_count": 0,
                    "deleted_chunks_count": 0,
                },
            }

        # 检测内容是否变更
        old_content_hash = old_version.get("content_hash")
        content_changed = new_content_hash != old_content_hash

        if not content_changed:
            return {
                "is_new": False,
                "has_changes": False,
                "content_changed": False,
                "new_chunks": [],
                "updated_chunks": [],
                "deleted_chunks": [],
                "unchanged_chunks": list(range(len(new_chunks))),
                "change_summary": {
                    "total_chunks": len(new_chunks),
                    "new_chunks_count": 0,
                    "changed_chunks_count": 0,
                    "deleted_chunks_count": 0,
                },
            }

        # 检测分块级别的变更
        old_chunk_hashes = old_version.get("chunk_hashes", [])

        # 查找新增、更新、删除的分块
        new_chunks_indices = []
        updated_chunks_indices = []
        deleted_chunks_indices = []
        unchanged_chunks_indices = []

        old_hash_to_index = {h: i for i, h in enumerate(old_chunk_hashes)}
        new_hash_to_index = {h: i for i, h in enumerate(new_chunk_hashes)}

        # 检测新增和更新的分块
        for i, new_hash in enumerate(new_chunk_hashes):
            if new_hash not in old_hash_to_index:
                # 新分块
                new_chunks_indices.append(i)
            else:
                # 分块存在但位置可能变化
                old_index = old_hash_to_index[new_hash]
                if old_index != i:
                    updated_chunks_indices.append(i)
                else:
                    unchanged_chunks_indices.append(i)

        # 检测删除的分块
        for i, old_hash in enumerate(old_chunk_hashes):
            if old_hash not in new_hash_to_index:
                deleted_chunks_indices.append(i)

        return {
            "is_new": False,
            "has_changes": True,
            "content_changed": content_changed,
            "new_chunks": new_chunks_indices,
            "updated_chunks": updated_chunks_indices,
            "deleted_chunks": deleted_chunks_indices,
            "unchanged_chunks": unchanged_chunks_indices,
            "change_summary": {
                "total_chunks": len(new_chunks),
                "new_chunks_count": len(new_chunks_indices),
                "changed_chunks_count": len(updated_chunks_indices),
                "deleted_chunks_count": len(deleted_chunks_indices),
                "unchanged_chunks_count": len(unchanged_chunks_indices),
            },
            "old_version": old_version.get("version"),
            "old_content_hash": old_content_hash,
            "new_content_hash": new_content_hash,
        }

    async def incremental_update(
        self,
        document_id: str,
        new_content: str,
        new_chunks: list[str],
        vector_service,
        metadata: dict | None = None,
    ) -> dict:
        """
        增量更新文档索引

        Args:
            document_id: 文档ID
            new_content: 新内容
            new_chunks: 新分块列表
            vector_service: 向量服务（用于更新向量索引）
            metadata: 元数据

        Returns:
            更新结果
        """
        start_time = time.time()

        try:
            # 检测变更
            changes = await self.detect_changes(document_id, new_content, new_chunks)

            if not changes["has_changes"]:
                logger.info(f"Document {document_id} has no changes, skipping update")
                return {
                    "success": True,
                    "document_id": document_id,
                    "action": "skipped",
                    "reason": "no_changes",
                    "elapsed_time": time.time() - start_time,
                }

            # 原子更新操作
            update_tasks = []

            # 1. 删除旧分块（如果有）
            if changes["deleted_chunks"]:
                deleted_chunk_ids = [f"{document_id}_chunk_{i}" for i in changes["deleted_chunks"]]
                delete_result = await vector_service.delete_vectors(deleted_chunk_ids)
                update_tasks.append(
                    {
                        "task": "delete",
                        "chunk_count": len(deleted_chunk_ids),
                        "result": delete_result,
                    }
                )

            # 2. 添加新分块
            if changes["new_chunks"]:
                new_chunk_contents = [new_chunks[i] for i in changes["new_chunks"]]
                new_chunk_ids = [f"{document_id}_chunk_{i}" for i in changes["new_chunks"]]

                insert_result = await vector_service.insert_chunks(
                    chunk_ids=new_chunk_ids,
                    chunk_contents=new_chunk_contents,
                    metadata=metadata,
                )
                update_tasks.append(
                    {
                        "task": "insert",
                        "chunk_count": len(new_chunk_ids),
                        "result": insert_result,
                    }
                )

            # 3. 更新变更的分块
            if changes["updated_chunks"]:
                updated_chunk_contents = [new_chunks[i] for i in changes["updated_chunks"]]
                updated_chunk_ids = [f"{document_id}_chunk_{i}" for i in changes["updated_chunks"]]

                # 先删除再插入（更新操作）
                await vector_service.delete_vectors(updated_chunk_ids)
                update_result = await vector_service.insert_chunks(
                    chunk_ids=updated_chunk_ids,
                    chunk_contents=updated_chunk_contents,
                    metadata=metadata,
                )
                update_tasks.append(
                    {
                        "task": "update",
                        "chunk_count": len(updated_chunk_ids),
                        "result": update_result,
                    }
                )

            # 4. 保存新版本信息
            new_content_hash = changes.get("new_content_hash")
            new_chunk_hashes = [await self.compute_content_hash(chunk) for chunk in new_chunks]

            await self.save_document_version(
                document_id=document_id,
                content_hash=new_content_hash,
                chunk_hashes=new_chunk_hashes,
                metadata=metadata,
            )

            elapsed_time = time.time() - start_time

            logger.info(
                f"Incremental update completed for {document_id}: "
                f"new={len(changes['new_chunks'])}, "
                f"updated={len(changes['updated_chunks'])}, "
                f"deleted={len(changes['deleted_chunks'])}, "
                f"time={elapsed_time:.2f}s"
            )

            return {
                "success": True,
                "document_id": document_id,
                "action": "updated",
                "changes": changes["change_summary"],
                "tasks": update_tasks,
                "elapsed_time": elapsed_time,
            }

        except Exception as e:
            logger.error(f"Incremental update failed for {document_id}: {e}", exc_info=True)
            return {
                "success": False,
                "document_id": document_id,
                "action": "failed",
                "error": str(e),
                "elapsed_time": time.time() - start_time,
            }

    async def bulk_check_changes(self, documents: list[dict[str, str]]) -> list[dict]:
        """
        批量检查文档变更

        Args:
            documents: 文档列表，每个文档包含 {id, content}

        Returns:
            变更检测结果列表
        """
        results = []

        for doc in documents:
            doc_id = doc.get("id")
            content = doc.get("content", "")

            content_hash = await self.compute_content_hash(content)
            old_version = await self.get_document_version(doc_id)

            if not old_version:
                status = "new"
            elif old_version.get("content_hash") == content_hash:
                status = "unchanged"
            else:
                status = "changed"

            results.append(
                {
                    "document_id": doc_id,
                    "status": status,
                    "old_hash": old_version.get("content_hash") if old_version else None,
                    "new_hash": content_hash,
                    "old_version": old_version.get("version") if old_version else None,
                }
            )

        return results

    async def get_statistics(self) -> dict:
        """
        获取增量索引统计信息

        Returns:
            统计信息
        """
        try:
            # 扫描所有版本键
            version_keys = []
            cursor = 0

            while True:
                cursor, keys = await self.redis.scan(
                    cursor, match=f"{self.version_key_prefix}*", count=100
                )
                version_keys.extend(keys)

                if cursor == 0:
                    break

            return {
                "total_versions": len(version_keys),
                "version_key_prefix": self.version_key_prefix,
                "ttl_seconds": self.version_ttl,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}
