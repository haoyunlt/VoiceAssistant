"""
Entity Linking Service - 实体链接服务

跨文档实体对齐与合并，解决实体重复问题
"""

import asyncio
import logging
from typing import Any

import numpy as np

from app.common.exceptions import EntityLinkingError, EntityMergeError
from app.core.metrics import (
    entities_merged_total,
    entity_linking_total,
)

logger = logging.getLogger(__name__)


class EntityLinkingService:
    """实体链接服务"""

    def __init__(
        self,
        neo4j_client,
        embedding_service,
        text_similarity_threshold: float = 0.90,
        embedding_similarity_threshold: float = 0.85,
    ):
        """
        初始化实体链接服务

        Args:
            neo4j_client: Neo4j客户端
            embedding_service: Embedding服务
            text_similarity_threshold: 文本相似度阈值
            embedding_similarity_threshold: 向量相似度阈值
        """
        self.neo4j = neo4j_client
        self.embedding_service = embedding_service
        self.text_threshold = text_similarity_threshold
        self.embedding_threshold = embedding_similarity_threshold

    async def link_entities_in_document(
        self, document_id: str, method: str = "hybrid"
    ) -> dict[str, Any]:
        """
        对文档内的实体进行链接

        Args:
            document_id: 文档ID
            method: 链接方法 (text/embedding/hybrid)

        Returns:
            链接结果
        """
        try:
            logger.info(f"Starting entity linking for document {document_id}")

            # 1. 获取文档所有实体
            entities = await self._get_document_entities(document_id)
            logger.info(f"Found {len(entities)} entities in document")

            if len(entities) < 2:
                return {"merged_count": 0, "entities_count": len(entities)}

            # 2. 根据方法选择链接策略
            if method == "text":
                merge_pairs = await self._find_text_similar_pairs(entities)
            elif method == "embedding":
                merge_pairs = await self._find_embedding_similar_pairs(entities)
            else:  # hybrid
                text_pairs = await self._find_text_similar_pairs(entities)
                embedding_pairs = await self._find_embedding_similar_pairs(entities)
                merge_pairs = self._combine_pairs(text_pairs, embedding_pairs)

            logger.info(f"Found {len(merge_pairs)} entity pairs to merge")

            # 3. 执行合并
            merged_count = await self._merge_entity_pairs(merge_pairs, document_id)

            entity_linking_total.labels(status="success").inc()

            return {
                "success": True,
                "document_id": document_id,
                "entities_before": len(entities),
                "merged_count": merged_count,
                "entities_after": len(entities) - merged_count,
            }

        except Exception as e:
            logger.error(f"Entity linking failed for document {document_id}: {e}")
            entity_linking_total.labels(status="failure").inc()
            raise EntityLinkingError(f"Failed to link entities: {e}", document_id=document_id) from e

    async def link_entities_across_documents(
        self, document_ids: list[str], method: str = "hybrid"
    ) -> dict[str, Any]:
        """
        跨文档实体链接

        Args:
            document_ids: 文档ID列表
            method: 链接方法

        Returns:
            链接结果
        """
        try:
            logger.info(f"Starting cross-document entity linking for {len(document_ids)} documents")

            # 并行处理每个文档
            results = await asyncio.gather(
                *[self.link_entities_in_document(doc_id, method) for doc_id in document_ids],
                return_exceptions=True,
            )

            # 汇总结果
            total_merged = 0
            successful_docs = 0

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Document linking failed: {result}")
                else:
                    total_merged += result.get("merged_count", 0)
                    successful_docs += 1

            return {
                "success": True,
                "documents_processed": successful_docs,
                "total_documents": len(document_ids),
                "total_merged": total_merged,
            }

        except Exception as e:
            logger.error(f"Cross-document entity linking failed: {e}")
            raise EntityLinkingError(f"Failed to link entities across documents: {e}") from e

    async def _get_document_entities(self, document_id: str) -> list[dict[str, Any]]:
        """获取文档所有实体"""
        query = """
        MATCH (n:Entity)
        WHERE n.document_id = $document_id
        RETURN elementId(n) as id, n.text as text, n.label as label,
               n.confidence as confidence
        """
        results = await self.neo4j.execute_query(query, {"document_id": document_id})

        return [
            {
                "id": r["id"],
                "text": r["text"],
                "label": r["label"],
                "confidence": r.get("confidence", 1.0),
            }
            for r in results
        ]

    async def _find_text_similar_pairs(
        self, entities: list[dict[str, Any]]
    ) -> list[tuple[str, str, float]]:
        """基于文本相似度查找相似实体对"""
        pairs = []

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                # 只比较相同类型的实体
                if e1["label"] != e2["label"]:
                    continue

                similarity = self._text_similarity(e1["text"], e2["text"])

                if similarity >= self.text_threshold:
                    pairs.append((e1["id"], e2["id"], similarity))
                    logger.debug(
                        f"Text similarity: '{e1['text']}' <-> '{e2['text']}' = {similarity:.3f}"
                    )

        return pairs

    async def _find_embedding_similar_pairs(
        self, entities: list[dict[str, Any]]
    ) -> list[tuple[str, str, float]]:
        """基于Embedding相似度查找相似实体对"""
        if len(entities) < 2:
            return []

        try:
            # 批量获取embeddings
            texts = [e["text"] for e in entities]
            embeddings = await self.embedding_service.get_embeddings_batch(texts)

            pairs = []

            for i, e1 in enumerate(entities):
                for j, e2 in enumerate(entities[i + 1 :], i + 1):
                    # 只比较相同类型的实体
                    if e1["label"] != e2["label"]:
                        continue

                    similarity = self._cosine_similarity(embeddings[i], embeddings[j])

                    if similarity >= self.embedding_threshold:
                        pairs.append((e1["id"], e2["id"], similarity))
                        logger.debug(
                            f"Embedding similarity: '{e1['text']}' <-> '{e2['text']}' = {similarity:.3f}"
                        )

            return pairs

        except Exception as e:
            logger.warning(f"Embedding similarity calculation failed: {e}")
            return []

    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（编辑距离）"""
        # 简化版：基于Levenshtein距离
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if text1 == text2:
            return 1.0

        # 计算编辑距离
        m, n = len(text1), len(text2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if text1[i - 1] == text2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1

        distance = dp[m][n]
        max_len = max(m, n)
        similarity = 1 - (distance / max_len) if max_len > 0 else 0.0

        return similarity

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _combine_pairs(
        self,
        text_pairs: list[tuple[str, str, float]],
        embedding_pairs: list[tuple[str, str, float]],
    ) -> list[tuple[str, str, float]]:
        """合并两种方法的结果（取交集）"""
        text_set = {(p[0], p[1]) for p in text_pairs}
        embedding_set = {(p[0], p[1]) for p in embedding_pairs}

        # 取交集
        common_pairs = text_set & embedding_set

        # 构建结果（取两种方法的平均分数）
        text_dict = {(p[0], p[1]): p[2] for p in text_pairs}
        embedding_dict = {(p[0], p[1]): p[2] for p in embedding_pairs}

        result = []
        for pair in common_pairs:
            avg_score = (text_dict[pair] + embedding_dict[pair]) / 2
            result.append((pair[0], pair[1], avg_score))

        return result

    async def _merge_entity_pairs(
        self, pairs: list[tuple[str, str, float]], _document_id: str
    ) -> int:
        """合并实体对"""
        merged_count = 0

        for source_id, target_id, similarity in pairs:
            try:
                await self._merge_entities(source_id, target_id)
                merged_count += 1
                entities_merged_total.labels(method="hybrid").inc()

                logger.info(
                    f"Merged entities: {source_id} -> {target_id} (similarity={similarity:.3f})"
                )

            except Exception as e:
                logger.error(f"Failed to merge entities {source_id} -> {target_id}: {e}")

        return merged_count

    async def _merge_entities(self, source_id: str, target_id: str):
        """
        合并两个实体

        将source_id的所有关系转移到target_id，然后删除source_id
        """
        try:
            # 1. 转移所有出边
            await self.neo4j.execute_query(
                """
                MATCH (source)-[r]->(target)
                WHERE elementId(source) = $source_id
                WITH source, r, target, type(r) as relType, properties(r) as props
                MATCH (new_source)
                WHERE elementId(new_source) = $target_id
                MERGE (new_source)-[new_r:MERGED_FROM]->(target)
                SET new_r = props
                DELETE r
                """,
                {"source_id": source_id, "target_id": target_id},
            )

            # 2. 转移所有入边
            await self.neo4j.execute_query(
                """
                MATCH (source)<-[r]-(target)
                WHERE elementId(source) = $source_id
                WITH source, r, target, type(r) as relType, properties(r) as props
                MATCH (new_source)
                WHERE elementId(new_source) = $target_id
                MERGE (target)-[new_r:MERGED_FROM]->(new_source)
                SET new_r = props
                DELETE r
                """,
                {"source_id": source_id, "target_id": target_id},
            )

            # 3. 删除源实体
            await self.neo4j.execute_query(
                """
                MATCH (n)
                WHERE elementId(n) = $source_id
                DELETE n
                """,
                {"source_id": source_id},
            )

            logger.debug(f"Successfully merged {source_id} into {target_id}")

        except Exception as e:
            raise EntityMergeError(
                f"Failed to merge entities: {e}",
                source_id=source_id,
                target_id=target_id,
            ) from e


# 全局实例
_entity_linking_service: EntityLinkingService | None = None


def get_entity_linking_service(neo4j_client, embedding_service) -> EntityLinkingService:
    """
    获取实体链接服务实例（单例）

    Args:
        neo4j_client: Neo4j客户端
        embedding_service: Embedding服务

    Returns:
        EntityLinkingService实例
    """
    global _entity_linking_service

    if _entity_linking_service is None:
        _entity_linking_service = EntityLinkingService(neo4j_client, embedding_service)

    return _entity_linking_service
