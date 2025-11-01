"""
基于向量相似度的实体合并服务

提供智能实体合并功能:
- 向量相似度检测
- 批量实体合并
- 合并规则配置
- 合并审计日志
"""

import logging
import time

import numpy as np

logger = logging.getLogger(__name__)


class EntitySimilarityMerger:
    """基于向量相似度的实体合并器"""

    def __init__(
        self,
        neo4j_client,
        embedding_service,
        similarity_threshold: float = 0.90,
        min_confidence: float = 0.85,
        require_type_match: bool = True,
    ):
        """
        初始化实体相似度合并器

        Args:
            neo4j_client: Neo4j客户端
            embedding_service: Embedding服务
            similarity_threshold: 相似度阈值
            min_confidence: 最小置信度
            require_type_match: 是否要求类型匹配
        """
        self.neo4j = neo4j_client
        self.embedding = embedding_service
        self.similarity_threshold = similarity_threshold
        self.min_confidence = min_confidence
        self.require_type_match = require_type_match

        logger.info(
            f"EntitySimilarityMerger initialized: "
            f"threshold={similarity_threshold}, "
            f"min_confidence={min_confidence}, "
            f"require_type_match={require_type_match}"
        )

    async def find_duplicate_candidates(
        self, entity_type: str | None = None, _batch_size: int = 100, max_candidates: int = 1000
    ) -> list[dict]:
        """
        查找重复实体候选

        Args:
            entity_type: 实体类型过滤
            batch_size: 批处理大小
            max_candidates: 最大候选数

        Returns:
            重复候选列表
        """
        try:
            # 1. 获取实体列表
            if entity_type:
                cypher = """
                MATCH (e:Entity {type: $type})
                RETURN e.id as id, e.name as name, e.type as type,
                       e.description as description
                LIMIT $max
                """
                params = {"type": entity_type, "max": max_candidates}
            else:
                cypher = """
                MATCH (e:Entity)
                RETURN e.id as id, e.name as name, e.type as type,
                       e.description as description
                LIMIT $max
                """
                params = {"max": max_candidates}

            entities = await self.neo4j.query(cypher, params)

            if not entities:
                return []

            logger.info(f"Analyzing {len(entities)} entities for duplicates")

            # 2. 生成实体文本（name + description）
            entity_texts = []
            entity_ids = []
            entity_info = {}

            for row in entities:
                entity_id = row["id"]
                name = row["name"]
                desc = row.get("description", "")
                entity_type_val = row.get("type", "")

                # 组合文本用于向量化
                text = f"{name}. {desc}" if desc else name
                entity_texts.append(text)
                entity_ids.append(entity_id)
                entity_info[entity_id] = {
                    "name": name,
                    "type": entity_type_val,
                    "description": desc,
                }

            # 3. 批量向量化
            logger.info("Computing embeddings for entities")
            embeddings = await self.embedding.encode(entity_texts, normalize=True)
            embeddings_array = np.array(embeddings)

            # 4. 计算相似度矩阵
            logger.info("Computing similarity matrix")
            similarity_matrix = np.dot(embeddings_array, embeddings_array.T)

            # 5. 查找高相似度对
            candidates = []
            processed = set()

            for i in range(len(entity_ids)):
                if entity_ids[i] in processed:
                    continue

                for j in range(i + 1, len(entity_ids)):
                    if entity_ids[j] in processed:
                        continue

                    similarity = float(similarity_matrix[i][j])

                    if similarity >= self.similarity_threshold:
                        # 检查类型匹配
                        if self.require_type_match:
                            type1 = entity_info[entity_ids[i]]["type"]
                            type2 = entity_info[entity_ids[j]]["type"]
                            if type1 != type2:
                                continue

                        candidates.append(
                            {
                                "entity1_id": entity_ids[i],
                                "entity1_name": entity_info[entity_ids[i]]["name"],
                                "entity1_type": entity_info[entity_ids[i]]["type"],
                                "entity2_id": entity_ids[j],
                                "entity2_name": entity_info[entity_ids[j]]["name"],
                                "entity2_type": entity_info[entity_ids[j]]["type"],
                                "similarity": similarity,
                                "confidence": self._calculate_confidence(
                                    entity_info[entity_ids[i]],
                                    entity_info[entity_ids[j]],
                                    similarity,
                                ),
                            }
                        )

                        processed.add(entity_ids[j])

            # 按相似度排序
            candidates.sort(key=lambda x: x["similarity"], reverse=True)

            logger.info(f"Found {len(candidates)} duplicate candidates")

            return candidates

        except Exception as e:
            logger.error(f"Failed to find duplicate candidates: {e}", exc_info=True)
            return []

    def _calculate_confidence(
        self, entity1: dict, entity2: dict, vector_similarity: float
    ) -> float:
        """
        计算合并置信度

        综合考虑:
        - 向量相似度
        - 名称相似度
        - 类型匹配
        - 描述完整性
        """
        scores = []
        weights = []

        # 1. 向量相似度 (40%)
        scores.append(vector_similarity)
        weights.append(0.4)

        # 2. 名称相似度 (30%)
        name1 = entity1["name"].lower()
        name2 = entity2["name"].lower()

        if name1 == name2:
            name_sim = 1.0
        elif name1 in name2 or name2 in name1:
            name_sim = 0.8
        else:
            # Jaccard相似度
            set1 = set(name1)
            set2 = set(name2)
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            name_sim = intersection / union if union > 0 else 0

        scores.append(name_sim)
        weights.append(0.3)

        # 3. 类型匹配 (20%)
        type_match = 1.0 if entity1["type"] == entity2["type"] else 0.0
        scores.append(type_match)
        weights.append(0.2)

        # 4. 描述完整性 (10%)
        desc1 = entity1.get("description", "")
        desc2 = entity2.get("description", "")
        desc_score = 1.0 if (desc1 and desc2) else 0.5
        scores.append(desc_score)
        weights.append(0.1)

        # 加权平均
        confidence = sum(s * w for s, w in zip(scores, weights, strict=False))

        return confidence

    async def auto_merge_duplicates(
        self,
        entity_type: str | None = None,
        min_confidence: float | None = None,
        dry_run: bool = True,
        max_merges: int = 100,
    ) -> dict:
        """
        自动合并重复实体

        Args:
            entity_type: 实体类型过滤
            min_confidence: 最小置信度阈值
            dry_run: 是否仅模拟（不实际合并）
            max_merges: 最大合并数量

        Returns:
            合并结果统计
        """
        try:
            start_time = time.time()

            min_conf = min_confidence or self.min_confidence

            # 1. 查找候选
            candidates = await self.find_duplicate_candidates(
                entity_type=entity_type, max_candidates=1000
            )

            # 2. 过滤低置信度候选
            high_confidence_candidates = [c for c in candidates if c["confidence"] >= min_conf]

            logger.info(
                f"Found {len(high_confidence_candidates)} high-confidence duplicates "
                f"(threshold={min_conf})"
            )

            # 3. 限制合并数量
            to_merge = high_confidence_candidates[:max_merges]

            # 4. 执行合并
            merged_count = 0
            failed_count = 0
            merge_results = []

            if not dry_run:
                for candidate in to_merge:
                    try:
                        result = await self._merge_entity_pair(
                            candidate["entity1_id"], candidate["entity2_id"]
                        )

                        if result["success"]:
                            merged_count += 1
                            merge_results.append({**candidate, "merge_result": result})
                        else:
                            failed_count += 1

                    except Exception as e:
                        logger.error(f"Failed to merge entities: {e}")
                        failed_count += 1

            elapsed = time.time() - start_time

            return {
                "success": True,
                "dry_run": dry_run,
                "candidates_found": len(candidates),
                "high_confidence_candidates": len(high_confidence_candidates),
                "merges_performed": merged_count,
                "merges_failed": failed_count,
                "elapsed_time": elapsed,
                "merge_details": merge_results if not dry_run else to_merge,
            }

        except Exception as e:
            logger.error(f"Auto merge failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _merge_entity_pair(self, source_id: str, target_id: str) -> dict:
        """
        合并一对实体

        Args:
            source_id: 源实体ID（将被删除）
            target_id: 目标实体ID（保留）

        Returns:
            合并结果
        """
        try:
            # 转移所有关系
            cypher_merge = """
            // 1. 转移出边
            MATCH (s:Entity {id: $source_id})-[r]->(other)
            WHERE other.id <> $target_id
            WITH s, r, other, type(r) as rel_type, properties(r) as props
            MATCH (t:Entity {id: $target_id})
            MERGE (t)-[new_r:RELATES]->(other)
            SET new_r = props, new_r.type = rel_type,
                new_r.merged_from = $source_id,
                new_r.merged_at = timestamp()
            DELETE r

            WITH count(*) as out_count

            // 2. 转移入边
            MATCH (other)-[r]->(s:Entity {id: $source_id})
            WHERE other.id <> $target_id
            WITH s, r, other, type(r) as rel_type, properties(r) as props, out_count
            MATCH (t:Entity {id: $target_id})
            MERGE (other)-[new_r:RELATES]->(t)
            SET new_r = props, new_r.type = rel_type,
                new_r.merged_from = $source_id,
                new_r.merged_at = timestamp()
            DELETE r

            WITH count(*) as in_count, out_count

            // 3. 删除源实体
            MATCH (s:Entity {id: $source_id})
            DELETE s

            RETURN out_count, in_count
            """

            result = await self.neo4j.query(
                cypher_merge, {"source_id": source_id, "target_id": target_id}
            )

            if result:
                out_count = result[0].get("out_count", 0)
                in_count = result[0].get("in_count", 0)

                logger.info(
                    f"Merged {source_id} into {target_id}: "
                    f"{out_count + in_count} relationships transferred"
                )

                return {
                    "success": True,
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationships_transferred": out_count + in_count,
                }
            else:
                return {"success": False, "error": "No result returned from merge query"}

        except Exception as e:
            logger.error(f"Failed to merge entity pair: {e}")
            return {"success": False, "error": str(e)}

    async def preview_merge(self, source_id: str, target_id: str) -> dict:
        """
        预览合并效果（不实际执行）

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID

        Returns:
            预览结果
        """
        try:
            # 获取实体信息
            cypher_info = """
            MATCH (s:Entity {id: $source_id})
            MATCH (t:Entity {id: $target_id})
            OPTIONAL MATCH (s)-[r_out]->()
            OPTIONAL MATCH ()-[r_in]->(s)
            RETURN s, t, count(DISTINCT r_out) as out_rels, count(DISTINCT r_in) as in_rels
            """

            result = await self.neo4j.query(
                cypher_info, {"source_id": source_id, "target_id": target_id}
            )

            if not result:
                return {"success": False, "error": "One or both entities not found"}

            row = result[0]
            source_entity = row["s"]
            target_entity = row["t"]
            out_rels = row["out_rels"]
            in_rels = row["in_rels"]

            # 计算合并置信度
            confidence = self._calculate_confidence(
                {
                    "name": source_entity.get("name"),
                    "type": source_entity.get("type"),
                    "description": source_entity.get("description", ""),
                },
                {
                    "name": target_entity.get("name"),
                    "type": target_entity.get("type"),
                    "description": target_entity.get("description", ""),
                },
                0.9,  # 假设向量相似度
            )

            return {
                "success": True,
                "source_entity": {
                    "id": source_id,
                    "name": source_entity.get("name"),
                    "type": source_entity.get("type"),
                    "relationships": out_rels + in_rels,
                },
                "target_entity": {
                    "id": target_id,
                    "name": target_entity.get("name"),
                    "type": target_entity.get("type"),
                },
                "confidence": confidence,
                "impact": {
                    "relationships_to_transfer": out_rels + in_rels,
                    "source_will_be_deleted": True,
                },
            }

        except Exception as e:
            logger.error(f"Failed to preview merge: {e}")
            return {"success": False, "error": str(e)}
