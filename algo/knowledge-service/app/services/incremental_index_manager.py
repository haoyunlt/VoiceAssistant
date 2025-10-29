"""
Incremental Index Manager - 增量索引管理器

支持文档的增量更新、实时索引和一致性保证
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """变更类型"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class DocumentChange:
    """文档变更记录"""

    def __init__(
        self,
        document_id: str,
        change_type: ChangeType,
        content: str | None = None,
        metadata: dict | None = None,
    ):
        self.document_id = document_id
        self.change_type = change_type
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now()


class IncrementalIndexManager:
    """增量索引管理器"""

    def __init__(
        self,
        neo4j_client,
        graphrag_service,
        kafka_producer=None,
        redis_client=None,
    ):
        """
        初始化增量索引管理器

        Args:
            neo4j_client: Neo4j客户端
            graphrag_service: GraphRAG服务
            kafka_producer: Kafka生产者（可选）
            redis_client: Redis客户端（用于分布式锁）
        """
        self.neo4j = neo4j_client
        self.graphrag = graphrag_service
        self.kafka = kafka_producer
        self.redis = redis_client
        self._processing_lock = asyncio.Lock()

    async def on_document_change(
        self, change: DocumentChange, domain: str = "general"
    ) -> dict[str, Any]:
        """
        处理文档变更事件

        Args:
            change: 文档变更
            domain: 领域

        Returns:
            处理结果
        """
        async with self._processing_lock:
            logger.info(f"Processing document change: {change.document_id} ({change.change_type})")

            try:
                if change.change_type == ChangeType.CREATE:
                    result = await self._handle_create(change, domain)
                elif change.change_type == ChangeType.UPDATE:
                    result = await self._handle_update(change, domain)
                elif change.change_type == ChangeType.DELETE:
                    result = await self._handle_delete(change)
                else:
                    raise ValueError(f"Unknown change type: {change.change_type}")

                # 发布更新事件
                if self.kafka:
                    await self._publish_update_event(change, result)

                return result

            except Exception as e:
                logger.error(f"Failed to process document change: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

    async def _handle_create(self, change: DocumentChange, domain: str) -> dict[str, Any]:
        """处理文档创建"""
        logger.info(f"Creating index for new document: {change.document_id}")

        # 获取文档chunks（假设已由indexing-service生成）
        chunks = await self._fetch_document_chunks(change.document_id)

        # 构建分层索引
        result = await self.graphrag.build_hierarchical_index(change.document_id, chunks, domain)

        return {
            "success": result.get("success", False),
            "operation": "create",
            "document_id": change.document_id,
            "entities_count": result.get("entities_count", 0),
            "relations_count": result.get("relations_count", 0),
        }

    async def _handle_update(self, change: DocumentChange, domain: str) -> dict[str, Any]:
        """处理文档更新（增量更新）"""
        logger.info(f"Incrementally updating document: {change.document_id}")

        start_time = datetime.now()

        # Step 1: 获取旧实体和关系
        old_entities = await self._get_document_entities(change.document_id)
        old_entity_texts = {e["text"] for e in old_entities}

        logger.info(f"Old entities: {len(old_entities)}")

        # Step 2: 重新提取新实体和关系
        chunks = await self._fetch_document_chunks(change.document_id)
        await self.graphrag.build_hierarchical_index(
            change.document_id, chunks, domain
        )

        new_entities = await self._get_document_entities(change.document_id)
        new_entity_texts = {e["text"] for e in new_entities}

        logger.info(f"New entities: {len(new_entities)}")

        # Step 3: 计算差异
        entities_added = new_entity_texts - old_entity_texts
        entities_removed = old_entity_texts - new_entity_texts
        entities_unchanged = new_entity_texts & old_entity_texts

        logger.info(
            f"Diff: +{len(entities_added)}, -{len(entities_removed)}, ={len(entities_unchanged)}"
        )

        # Step 4: 处理删除的实体（移除文档引用）
        for entity_text in entities_removed:
            await self._remove_entity_reference(entity_text, change.document_id)

        # Step 5: 更新受影响的社区（局部重算）
        affected_entities = entities_added | entities_removed
        if affected_entities:
            await self._update_affected_communities(affected_entities, domain)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Incremental update completed in {elapsed:.2f}s")

        return {
            "success": True,
            "operation": "update",
            "document_id": change.document_id,
            "entities_added": len(entities_added),
            "entities_removed": len(entities_removed),
            "entities_unchanged": len(entities_unchanged),
            "elapsed_seconds": elapsed,
        }

    async def _handle_delete(self, change: DocumentChange) -> dict[str, Any]:
        """处理文档删除"""
        logger.info(f"Deleting document index: {change.document_id}")

        # Step 1: 获取文档的所有实体
        entities = await self._get_document_entities(change.document_id)

        # Step 2: 移除所有实体引用
        for entity in entities:
            await self._remove_entity_reference(entity["text"], change.document_id)

        # Step 3: 删除文档索引元数据
        await self.neo4j.execute_query(
            """
            MATCH (d:DocumentIndex {document_id: $document_id})
            DELETE d
            """,
            {"document_id": change.document_id},
        )

        # Step 4: 清理孤立实体（没有任何文档引用的实体）
        orphan_count = await self._cleanup_orphan_entities()

        logger.info(
            f"Document {change.document_id} deleted, cleaned up {orphan_count} orphan entities"
        )

        return {
            "success": True,
            "operation": "delete",
            "document_id": change.document_id,
            "entities_removed": len(entities),
            "orphans_cleaned": orphan_count,
        }

    async def _get_document_entities(self, document_id: str) -> list[dict[str, Any]]:
        """获取文档的所有实体"""
        try:
            results = await self.neo4j.execute_query(
                """
                MATCH (n)
                WHERE n.document_id = $document_id
                RETURN n.text as text, n.label as label, elementId(n) as id
                """,
                {"document_id": document_id},
            )

            entities = []
            for record in results:
                entities.append(
                    {
                        "id": record["id"],
                        "text": record["text"],
                        "label": record["label"],
                    }
                )

            return entities

        except Exception as e:
            logger.error(f"Failed to get document entities: {e}")
            return []

    async def _remove_entity_reference(self, entity_text: str, document_id: str):
        """移除实体的文档引用"""
        try:
            # 查找实体节点
            await self.neo4j.execute_query(
                """
                MATCH (n {text: $entity_text, document_id: $document_id})
                OPTIONAL MATCH (n)-[r]-()
                DELETE r, n
                """,
                {"entity_text": entity_text, "document_id": document_id},
            )

            logger.debug(f"Removed entity '{entity_text}' reference from document {document_id}")

        except Exception as e:
            logger.error(f"Failed to remove entity reference: {e}")

    async def _cleanup_orphan_entities(self, days_threshold: int = 30) -> int:
        """清理孤立实体"""
        try:
            # 删除没有任何关系的孤立节点
            result = await self.neo4j.execute_query(
                """
                MATCH (n)
                WHERE NOT (n)-[]-()
                WITH n, n.created_at as created_at
                WHERE created_at IS NULL OR
                      duration.between(datetime(created_at), datetime()).days > $days
                DELETE n
                RETURN count(n) as deleted_count
                """,
                {"days": days_threshold},
            )

            deleted_count = result[0]["deleted_count"] if result else 0
            logger.info(f"Cleaned up {deleted_count} orphan entities")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup orphan entities: {e}")
            return 0

    async def _update_affected_communities(self, affected_entities: set[str], domain: str):
        """更新受影响的社区"""
        try:
            # 找到包含这些实体的社区
            affected_community_ids = await self._find_affected_communities(affected_entities)

            logger.info(f"Updating {len(affected_community_ids)} affected communities")

            # 重新计算社区摘要
            for community_id in affected_community_ids:
                await self._recompute_community(community_id, domain)

        except Exception as e:
            logger.error(f"Failed to update affected communities: {e}")

    async def _find_affected_communities(self, entity_texts: set[str]) -> list[str]:
        """查找受影响的社区"""
        try:
            if not entity_texts:
                return []

            # 策略1: 查询 Neo4j 中维护的实体-社区映射表
            # 如果实体属于某个社区，返回该社区 ID
            
            # Cypher 查询：找到包含这些实体的所有社区
            query = """
            MATCH (e:Entity)-[:BELONGS_TO]->(c:Community)
            WHERE e.text IN $entity_texts
            RETURN DISTINCT c.id as community_id
            """
            
            results = await self.neo4j.execute_query(
                query,
                {"entity_texts": list(entity_texts)}
            )
            
            community_ids = [r["community_id"] for r in results if r.get("community_id")]
            
            logger.info(
                f"Found {len(community_ids)} affected communities "
                f"from {len(entity_texts)} changed entities"
            )
            
            return community_ids

        except Exception as e:
            logger.error(f"Failed to find affected communities: {e}", exc_info=True)
            return []

    async def _recompute_community(self, community_id: str, domain: str):
        """重新计算社区摘要"""
        try:
            # 1. 获取社区的所有实体
            entity_query = """
            MATCH (e:Entity)-[:BELONGS_TO]->(c:Community {id: $community_id})
            RETURN e.text as text, e.label as label
            """
            
            entity_results = await self.neo4j.execute_query(
                entity_query,
                {"community_id": community_id}
            )
            
            if not entity_results:
                logger.warning(f"Community {community_id} has no entities")
                return
            
            entities = [r["text"] for r in entity_results]
            
            # 2. 获取社区内的关系
            relation_query = """
            MATCH (e1:Entity)-[:BELONGS_TO]->(c:Community {id: $community_id}),
                  (e2:Entity)-[:BELONGS_TO]->(c),
                  (e1)-[r]->(e2)
            RETURN e1.text as source, type(r) as relation, e2.text as target
            LIMIT 100
            """
            
            relation_results = await self.neo4j.execute_query(
                relation_query,
                {"community_id": community_id}
            )
            
            # 3. 构建社区描述文本
            community_text = self._build_community_description(
                entities, relation_results
            )
            
            # 4. 使用 GraphRAG 服务生成摘要
            if self.graphrag:
                try:
                    summary = await self.graphrag.generate_community_summary(
                        community_id=community_id,
                        entities=entities,
                        relations=relation_results,
                        domain=domain
                    )
                except Exception as e:
                    logger.warning(f"GraphRAG summary generation failed: {e}")
                    # 降级：使用简单文本摘要
                    summary = f"Community with {len(entities)} entities"
            else:
                summary = f"Community with {len(entities)} entities"
            
            # 5. 更新社区节点的摘要属性
            update_query = """
            MATCH (c:Community {id: $community_id})
            SET c.summary = $summary,
                c.entity_count = $entity_count,
                c.updated_at = datetime()
            RETURN c
            """
            
            await self.neo4j.execute_query(
                update_query,
                {
                    "community_id": community_id,
                    "summary": summary,
                    "entity_count": len(entities)
                }
            )

            logger.info(
                f"Recomputed community {community_id}: "
                f"{len(entities)} entities, {len(relation_results)} relations"
            )

        except Exception as e:
            logger.error(f"Failed to recompute community: {e}", exc_info=True)

    def _build_community_description(
        self, entities: list[str], relations: list[dict]
    ) -> str:
        """构建社区描述文本用于摘要生成"""
        description = f"This community contains {len(entities)} entities"
        
        if entities:
            sample_entities = entities[:10]
            description += f": {', '.join(sample_entities)}"
            if len(entities) > 10:
                description += f" and {len(entities) - 10} more"
        
        if relations:
            description += f". It has {len(relations)} relationships"
            
            # 统计关系类型
            relation_types = {}
            for r in relations:
                rel_type = r.get("relation", "unknown")
                relation_types[rel_type] = relation_types.get(rel_type, 0) + 1
            
            top_relations = sorted(
                relation_types.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            if top_relations:
                rel_str = ", ".join([f"{rt}({count})" for rt, count in top_relations])
                description += f", including {rel_str}"
        
        return description

    async def _fetch_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        """获取文档的文本块"""
        try:
            import sys
            from pathlib import Path
            import httpx
            
            # 添加 common 路径
            common_path = Path(__file__).parent.parent.parent.parent / "common"
            if str(common_path) not in sys.path:
                sys.path.insert(0, str(common_path))
            
            from vector_store_client import VectorStoreClient
            
            # 初始化向量存储客户端
            vector_client = VectorStoreClient()
            
            # 注意：当前 VectorStoreClient 的 search 需要 query_vector
            # 这里我们需要通过 document_id 过滤获取所有 chunks
            # 简化策略：使用零向量 + document_id 过滤
            
            # 获取 embedding 维度（通常是 768 或 1024）
            embedding_dim = 768  # BGE-M3 默认维度
            dummy_vector = [0.0] * embedding_dim
            
            # 搜索该文档的所有 chunks（使用高 top_k）
            results = await vector_client.search(
                query_vector=dummy_vector,
                top_k=1000,  # 假设单文档不超过 1000 个 chunks
                filters=f'document_id == "{document_id}"'
            )
            
            chunks = []
            for result in results:
                chunks.append({
                    "chunk_id": result.get("chunk_id"),
                    "content": result.get("content"),
                    "metadata": result.get("metadata", {})
                })
            
            await vector_client.close()
            
            logger.info(f"Fetched {len(chunks)} chunks for document {document_id}")
            return chunks
            
        except Exception as e:
            logger.error(
                f"Failed to fetch chunks for {document_id}: {e}",
                exc_info=True
            )
            # 降级：返回空列表
            return []

    async def _publish_update_event(self, change: DocumentChange, result: dict[str, Any]):
        """发布更新事件到Kafka"""
        if not self.kafka:
            return

        try:
            event_data = {
                "document_id": change.document_id,
                "change_type": change.change_type.value,
                "timestamp": change.timestamp.isoformat(),
                "result": result,
            }

            await self.kafka.publish_event("kg.updated", event_data)
            logger.debug(f"Published update event for {change.document_id}")

        except Exception as e:
            logger.error(f"Failed to publish update event: {e}")

    async def batch_update(
        self, changes: list[DocumentChange], domain: str = "general"
    ) -> list[dict[str, Any]]:
        """
        批量处理文档变更

        Args:
            changes: 文档变更列表
            domain: 领域

        Returns:
            处理结果列表
        """
        logger.info(f"Batch processing {len(changes)} document changes")

        results = []
        for change in changes:
            result = await self.on_document_change(change, domain)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Batch update completed: {success_count}/{len(changes)} successful")

        return results

    async def rebuild_index(
        self, document_ids: list[str] | None = None, domain: str = "general"
    ) -> dict[str, Any]:
        """
        重建索引（全量或部分）

        Args:
            document_ids: 文档ID列表（None表示全部）
            domain: 领域

        Returns:
            重建结果
        """
        logger.info(
            f"Rebuilding index for {len(document_ids) if document_ids else 'all'} documents"
        )

        start_time = datetime.now()

        if document_ids is None:
            # 全量重建：清空所有索引
            await self._clear_all_indices()
            # 获取所有文档ID
            document_ids = await self._get_all_document_ids()

        # 批量重建
        results = []
        for doc_id in document_ids:
            change = DocumentChange(doc_id, ChangeType.CREATE)
            result = await self._handle_create(change, domain)
            results.append(result)

        elapsed = (datetime.now() - start_time).total_seconds()
        success_count = sum(1 for r in results if r.get("success"))

        logger.info(
            f"Index rebuild completed: {success_count}/{len(document_ids)} in {elapsed:.2f}s"
        )

        return {
            "success": True,
            "documents_processed": len(document_ids),
            "documents_successful": success_count,
            "elapsed_seconds": elapsed,
        }

    async def _clear_all_indices(self):
        """清空所有索引"""
        logger.warning("Clearing all indices")

        try:
            # 删除所有节点和关系
            await self.neo4j.execute_query("MATCH (n) DETACH DELETE n")
            logger.info("All indices cleared")

        except Exception as e:
            logger.error(f"Failed to clear indices: {e}")
            raise

    async def _get_all_document_ids(self) -> list[str]:
        """获取所有文档ID"""
        # 实际实现中，应该从数据库查询
        logger.warning("get_all_document_ids should query from database")
        return []

    async def get_index_stats(self) -> dict[str, Any]:
        """获取索引统计信息"""
        try:
            # 节点统计
            node_stats = await self.neo4j.execute_query(
                """
                MATCH (n)
                WITH labels(n)[0] as label, count(*) as count
                RETURN label, count
                ORDER BY count DESC
                """
            )

            # 关系统计
            rel_stats = await self.neo4j.execute_query(
                """
                MATCH ()-[r]->()
                WITH type(r) as rel_type, count(*) as count
                RETURN rel_type, count
                ORDER BY count DESC
                """
            )

            # 文档统计
            doc_stats = await self.neo4j.execute_query(
                """
                MATCH (d:DocumentIndex)
                RETURN count(d) as total_documents
                """
            )

            return {
                "nodes": [
                    {"label": record["label"], "count": record["count"]} for record in node_stats
                ],
                "relationships": [
                    {"type": record["rel_type"], "count": record["count"]} for record in rel_stats
                ],
                "documents": doc_stats[0]["total_documents"] if doc_stats else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {"error": str(e)}


# 全局实例
_incremental_index_manager: IncrementalIndexManager | None = None


def get_incremental_index_manager(
    neo4j_client, graphrag_service, kafka_producer=None, redis_client=None
) -> IncrementalIndexManager:
    """获取增量索引管理器实例（单例）"""
    global _incremental_index_manager

    if _incremental_index_manager is None:
        _incremental_index_manager = IncrementalIndexManager(
            neo4j_client, graphrag_service, kafka_producer, redis_client
        )

    return _incremental_index_manager
