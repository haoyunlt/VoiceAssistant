"""
实体消歧服务
使用向量相似度进行实体消歧和自动合并
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class EntityDisambiguationService:
    """实体消歧服务"""

    def __init__(
        self,
        neo4j_client,
        embedding_service=None,
        similarity_threshold: float = 0.85,
        auto_merge: bool = False,
    ):
        """
        初始化实体消歧服务

        Args:
            neo4j_client: Neo4j客户端
            embedding_service: 向量化服务（可选）
            similarity_threshold: 相似度阈值（0-1）
            auto_merge: 是否自动合并相似实体
        """
        self.neo4j = neo4j_client
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.auto_merge = auto_merge

        logger.info(
            f"EntityDisambiguationService initialized: "
            f"threshold={similarity_threshold}, auto_merge={auto_merge}"
        )

    async def compute_similarity(
        self, entity1: Dict, entity2: Dict
    ) -> float:
        """
        计算两个实体的相似度

        Args:
            entity1: 实体1
            entity2: 实体2

        Returns:
            相似度分数（0-1）
        """
        try:
            # 1. 名称字符串相似度
            name1 = entity1.get("name", "").lower()
            name2 = entity2.get("name", "").lower()

            if name1 == name2:
                name_similarity = 1.0
            else:
                # 使用Levenshtein距离
                name_similarity = self._string_similarity(name1, name2)

            # 2. 向量相似度（如果有embedding）
            vector_similarity = 0.0

            if "embedding" in entity1 and "embedding" in entity2:
                vec1 = np.array(entity1["embedding"])
                vec2 = np.array(entity2["embedding"])

                # 余弦相似度
                vector_similarity = self._cosine_similarity(vec1, vec2)

            # 3. 类型匹配
            type1 = entity1.get("type", "")
            type2 = entity2.get("type", "")
            type_match = 1.0 if type1 == type2 else 0.0

            # 4. 上下文相似度（基于描述）
            desc1 = entity1.get("description", "")
            desc2 = entity2.get("description", "")

            if desc1 and desc2 and self.embedding_service:
                # 使用embedding service计算描述相似度
                try:
                    context_similarity = await self.embedding_service.compute_similarity(
                        desc1, desc2
                    )
                except Exception as e:
                    logger.warning(f"Failed to compute description similarity: {e}")
                    context_similarity = 0.5
            else:
                context_similarity = 0.0

            # 综合相似度（加权平均）
            weights = {
                "name": 0.3,
                "vector": 0.4,
                "type": 0.2,
                "context": 0.1,
            }

            total_similarity = (
                name_similarity * weights["name"]
                + vector_similarity * weights["vector"]
                + type_match * weights["type"]
                + context_similarity * weights["context"]
            )

            return total_similarity

        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        计算字符串相似度（简化的Levenshtein）

        Args:
            s1: 字符串1
            s2: 字符串2

        Returns:
            相似度（0-1）
        """
        if not s1 or not s2:
            return 0.0

        # 简化实现：计算共同字符比例
        set1 = set(s1)
        set2 = set(s2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            余弦相似度（0-1）
        """
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # 归一化到[0, 1]
            return (similarity + 1) / 2

        except Exception as e:
            logger.error(f"Failed to compute cosine similarity: {e}")
            return 0.0

    async def find_similar_entities(
        self, entity_id: str, top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        查找相似实体

        Args:
            entity_id: 实体ID
            top_k: 返回前K个相似实体

        Returns:
            相似实体列表 [(entity_id, similarity_score)]
        """
        try:
            # 获取目标实体
            cypher_get = """
            MATCH (e:Entity)
            WHERE e.id = $entity_id
            RETURN e
            """
            result = await self.neo4j.query(cypher_get, {"entity_id": entity_id})

            if not result:
                logger.warning(f"Entity {entity_id} not found")
                return []

            target_entity = result[0]["e"]

            # 获取所有其他实体
            cypher_all = """
            MATCH (e:Entity)
            WHERE e.id <> $entity_id
            RETURN e
            LIMIT 1000
            """
            all_entities = await self.neo4j.query(cypher_all, {"entity_id": entity_id})

            # 计算相似度
            similarities = []

            for row in all_entities:
                candidate = row["e"]
                similarity = await self.compute_similarity(target_entity, candidate)

                if similarity >= self.similarity_threshold:
                    similarities.append((candidate["id"], similarity))

            # 排序并返回top_k
            similarities.sort(key=lambda x: x[1], reverse=True)

            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Failed to find similar entities: {e}", exc_info=True)
            return []

    async def merge_entities(
        self, source_entity_id: str, target_entity_id: str
    ) -> Dict:
        """
        合并两个实体

        将source实体的所有关系转移到target实体，然后删除source

        Args:
            source_entity_id: 源实体ID（将被删除）
            target_entity_id: 目标实体ID（保留）

        Returns:
            合并结果
        """
        try:
            # 1. 获取实体信息
            cypher_get = """
            MATCH (s:Entity {id: $source_id})
            MATCH (t:Entity {id: $target_id})
            RETURN s, t
            """
            result = await self.neo4j.query(
                cypher_get,
                {"source_id": source_entity_id, "target_id": target_entity_id},
            )

            if not result:
                return {
                    "success": False,
                    "error": "One or both entities not found",
                }

            source = result[0]["s"]
            target = result[0]["t"]

            # 2. 转移所有关系
            # 2.1 转移出边
            cypher_out = """
            MATCH (s:Entity {id: $source_id})-[r]->(other)
            WHERE other.id <> $target_id
            WITH s, r, other, type(r) as rel_type, properties(r) as props
            MATCH (t:Entity {id: $target_id})
            CREATE (t)-[new_r:RELATES]->(other)
            SET new_r = props, new_r.type = rel_type, new_r.merged_from = $source_id
            DELETE r
            RETURN count(new_r) as out_count
            """

            out_result = await self.neo4j.query(
                cypher_out,
                {"source_id": source_entity_id, "target_id": target_entity_id},
            )
            out_count = out_result[0]["out_count"] if out_result else 0

            # 2.2 转移入边
            cypher_in = """
            MATCH (other)-[r]->(s:Entity {id: $source_id})
            WHERE other.id <> $target_id
            WITH other, r, s, type(r) as rel_type, properties(r) as props
            MATCH (t:Entity {id: $target_id})
            CREATE (other)-[new_r:RELATES]->(t)
            SET new_r = props, new_r.type = rel_type, new_r.merged_from = $source_id
            DELETE r
            RETURN count(new_r) as in_count
            """

            in_result = await self.neo4j.query(
                cypher_in,
                {"source_id": source_entity_id, "target_id": target_entity_id},
            )
            in_count = in_result[0]["in_count"] if in_result else 0

            # 3. 合并属性（可选）
            # 这里简化处理，保留target的属性

            # 4. 删除source实体
            cypher_delete = """
            MATCH (s:Entity {id: $source_id})
            DELETE s
            """
            await self.neo4j.query(cypher_delete, {"source_id": source_entity_id})

            logger.info(
                f"Merged entity {source_entity_id} into {target_entity_id}: "
                f"out_edges={out_count}, in_edges={in_count}"
            )

            return {
                "success": True,
                "source_entity": source.get("name"),
                "target_entity": target.get("name"),
                "relationships_transferred": out_count + in_count,
                "out_edges": out_count,
                "in_edges": in_count,
            }

        except Exception as e:
            logger.error(f"Failed to merge entities: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def auto_merge_duplicates(
        self, entity_type: Optional[str] = None, dry_run: bool = True
    ) -> Dict:
        """
        自动合并重复实体

        Args:
            entity_type: 实体类型过滤（可选）
            dry_run: 是否仅模拟（不实际合并）

        Returns:
            合并结果统计
        """
        try:
            # 获取所有实体
            if entity_type:
                cypher = """
                MATCH (e:Entity {type: $type})
                RETURN e
                LIMIT 1000
                """
                params = {"type": entity_type}
            else:
                cypher = """
                MATCH (e:Entity)
                RETURN e
                LIMIT 1000
                """
                params = {}

            entities = await self.neo4j.query(cypher, params)

            # 查找重复实体
            duplicates = []
            processed = set()

            for i, row1 in enumerate(entities):
                entity1 = row1["e"]
                entity1_id = entity1["id"]

                if entity1_id in processed:
                    continue

                for row2 in entities[i + 1 :]:
                    entity2 = row2["e"]
                    entity2_id = entity2["id"]

                    if entity2_id in processed:
                        continue

                    # 计算相似度
                    similarity = await self.compute_similarity(entity1, entity2)

                    if similarity >= self.similarity_threshold:
                        duplicates.append(
                            {
                                "entity1_id": entity1_id,
                                "entity1_name": entity1.get("name"),
                                "entity2_id": entity2_id,
                                "entity2_name": entity2.get("name"),
                                "similarity": similarity,
                            }
                        )

                        processed.add(entity2_id)

            # 执行合并（如果不是dry_run）
            merged_count = 0

            if not dry_run:
                for dup in duplicates:
                    result = await self.merge_entities(
                        dup["entity2_id"], dup["entity1_id"]
                    )

                    if result["success"]:
                        merged_count += 1

            return {
                "success": True,
                "total_entities": len(entities),
                "duplicates_found": len(duplicates),
                "merged_count": merged_count,
                "dry_run": dry_run,
                "duplicates": duplicates,
            }

        except Exception as e:
            logger.error(f"Failed to auto merge duplicates: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def disambiguate_entity(
        self, entity_name: str, context: Optional[str] = None
    ) -> List[Dict]:
        """
        实体消歧（根据上下文选择正确的实体）

        Args:
            entity_name: 实体名称
            context: 上下文信息

        Returns:
            候选实体列表（按相关性排序）
        """
        try:
            # 查找同名实体
            cypher = """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
            RETURN e
            """
            candidates = await self.neo4j.query(cypher, {"name": entity_name})

            if not candidates:
                return []

            # 如果只有一个候选，直接返回
            if len(candidates) == 1:
                return [candidates[0]["e"]]

            # 如果有上下文，使用上下文消歧
            if context and self.embedding_service:
                # 使用embedding计算上下文相似度
                try:
                    # 计算context与每个候选实体描述的相似度
                    similarities = []

                    for row in candidates:
                        entity = row["e"]
                        description = entity.get("description", "")

                        if description:
                            similarity = await self.embedding_service.compute_similarity(
                                context, description
                            )
                        else:
                            similarity = 0.5  # 默认中等相似度

                        similarities.append((entity, similarity))

                    # 按相似度排序
                    similarities.sort(key=lambda x: x[1], reverse=True)

                    # 归一化置信度
                    total_sim = sum(sim for _, sim in similarities)
                    if total_sim > 0:
                        result = []
                        for entity, similarity in similarities:
                            result.append(
                                {
                                    "id": entity["id"],
                                    "name": entity.get("name"),
                                    "type": entity.get("type"),
                                    "description": entity.get("description"),
                                    "confidence": similarity / total_sim,
                                    "context_similarity": similarity
                                }
                            )
                        return result

                except Exception as e:
                    logger.error(f"Failed to compute context similarity: {e}")
                    # 降级到简单处理

            # 简化处理：返回所有候选（按类型分组）
            result = []
            for row in candidates:
                entity = row["e"]
                result.append(
                    {
                        "id": entity["id"],
                        "name": entity.get("name"),
                        "type": entity.get("type"),
                        "description": entity.get("description"),
                        "confidence": 1.0
                        / len(candidates),  # 简化：平均分配置信度
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to disambiguate entity: {e}", exc_info=True)
            return []
