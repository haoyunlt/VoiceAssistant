"""
GraphBuilder - 知识图谱构建器

提取实体和关系，构建知识图谱
"""

import asyncio
import logging

from app.core.entity_extractor import EntityExtractor, RelationExtractor

logger = logging.getLogger(__name__)


class GraphBuilder:
    """知识图谱构建器"""

    def __init__(
        self,
        neo4j_client,
        entity_extractor: EntityExtractor | None = None,
        relation_extractor: RelationExtractor | None = None,
    ):
        """初始化 GraphBuilder"""
        self.neo4j_client = neo4j_client
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.relation_extractor = relation_extractor or RelationExtractor()
        logger.info(
            "GraphBuilder initialized with entity_extractor=%s, relation_extractor=%s",
            self.entity_extractor.__class__.__name__,
            self.relation_extractor.__class__.__name__,
        )

    async def extract(self, text: str) -> tuple[list[dict], list[dict]]:
        """
        从文本中提取实体和关系

        Args:
            text: 输入文本

        Returns:
            (entities, relationships) 元组
        """
        entities = await self._extract_entities(text)
        relationships = await self._extract_relationships(text, entities)

        logger.info(
            "Extracted %s entities and %s relationships",
            len(entities),
            len(relationships),
        )

        return entities, relationships

    async def _extract_entities(self, text: str) -> list[dict]:
        """使用实体抽取器识别实体"""
        try:
            # EntityExtractor 是同步方法，使用线程池避免阻塞
            loop = asyncio.get_running_loop()
            entities = await loop.run_in_executor(
                None, self.entity_extractor.extract_entities_with_context, text
            )
            return entities
        except Exception as exc:
            logger.error("Entity extraction failed: %s", exc, exc_info=True)
            return []

    async def _extract_relationships(self, text: str, entities: list[dict]) -> list[dict]:
        """使用关系抽取器识别实体之间的关系"""
        if not entities:
            return []

        try:
            loop = asyncio.get_running_loop()
            relationships = await loop.run_in_executor(
                None, self.relation_extractor.extract_relations, text, entities
            )
            return relationships
        except Exception as exc:
            logger.error("Relation extraction failed: %s", exc, exc_info=True)
            return []

    async def build(
        self,
        entities: list[dict],
        relationships: list[dict],
        document_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, int]:
        """
        构建知识图谱

        Args:
            entities: 实体列表
            relationships: 关系列表
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            持久化统计信息
        """
        if not entities:
            logger.info("No entities to build graph for document %s", document_id)
            return {"entities_created": 0, "relations_created": 0}

        # 去重和过滤
        deduped_entities = self._deduplicate_entities(entities)
        filtered_relations = self._filter_relations(relationships)

        # 批量创建（同步方法，使用线程池）
        stats = await asyncio.get_running_loop().run_in_executor(
            None,
            self.neo4j_client.bulk_create_graph,
            deduped_entities,
            filtered_relations,
            document_id,
            tenant_id or "default",
        )

        logger.info(
            "Built graph for document %s: %s entities, %s relations",
            document_id,
            stats.get("entities_created", 0),
            stats.get("relations_created", 0),
        )

        return stats

    def _deduplicate_entities(self, entities: list[dict]) -> list[dict]:
        """去除重复实体并标准化"""
        seen = set()
        unique_entities: list[dict] = []

        for entity in entities:
            text = entity.get("text")
            label = entity.get("label", "")
            if not text:
                continue

            key = (text.lower(), label)
            if key in seen:
                continue

            seen.add(key)
            unique_entities.append(
                {
                    "text": text,
                    "label": label,
                    "confidence": float(entity.get("confidence", 1.0) or 1.0),
                }
            )

        return unique_entities

    def _filter_relations(
        self,
        relations: list[dict],
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """过滤低置信度关系并标准化字段"""
        filtered: list[dict] = []

        for relation in relations:
            confidence = float(relation.get("confidence", 0) or 0)
            if confidence < min_confidence:
                continue

            source = relation.get("source")
            target = relation.get("target")
            rel_type = relation.get("relation")
            if not (source and target and rel_type):
                continue

            filtered.append(
                {
                    "source": source,
                    "target": target,
                    "relation": rel_type,
                    "confidence": confidence,
                    "method": relation.get("method", "hybrid"),
                }
            )

        return filtered
