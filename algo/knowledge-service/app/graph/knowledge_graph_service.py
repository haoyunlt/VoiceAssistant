"""
Knowledge Graph Service - 知识图谱服务

整合实体提取、关系提取和 Neo4j 存储
"""

from typing import Any, Dict, List, Optional

import logging
from app.graph.entity_extractor import get_entity_extractor
from app.graph.neo4j_client import get_neo4j_client
from app.graph.relation_extractor import get_relation_extractor

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """知识图谱服务"""

    def __init__(self, kafka_producer=None):
        """初始化知识图谱服务"""
        self.entity_extractor = get_entity_extractor()
        self.relation_extractor = get_relation_extractor()
        self.neo4j_client = get_neo4j_client()
        self.kafka_producer = kafka_producer  # Kafka生产者（可选）

    async def extract_and_store(self, text: str, source: Optional[str] = None) -> Dict[str, Any]:
        """
        从文本提取知识并存储到图谱

        Args:
            text: 输入文本
            source: 数据来源（可选）

        Returns:
            提取和存储结果
        """
        try:
            # 1. 提取实体
            entities = self.entity_extractor.extract_entities(text)
            logger.info(f"Extracted {len(entities)} entities")

            # 2. 提取关系
            relations = self.relation_extractor.extract_relations(text, entities)
            logger.info(f"Extracted {len(relations)} relations")

            # 3. 存储到 Neo4j
            entity_ids = {}
            for entity in entities:
                node_properties = {
                    "text": entity["text"],
                    "label": entity["label"],
                    "confidence": entity.get("confidence", 1.0),
                }
                if source:
                    node_properties["source"] = source

                node_id = await self.neo4j_client.create_node(
                    label=entity["label"], properties=node_properties
                )

                if node_id:
                    entity_ids[entity["text"]] = node_id

                    # 发布实体创建事件
                    if self.kafka_producer:
                        try:
                            await self.kafka_producer.publish_entity_created(
                                entity_id=node_id,
                                tenant_id=node_properties.get("tenant_id", "default"),
                                entity_data={
                                    "name": entity["text"],
                                    "type": entity["label"],
                                    "description": "",
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Failed to publish entity created event: {e}")

            # 4. 存储关系
            stored_relations = 0
            for relation in relations:
                subject_id = entity_ids.get(relation["subject"])
                object_id = entity_ids.get(relation["object"])

                if subject_id and object_id:
                    rel_type = relation["predicate"].upper().replace(" ", "_")
                    success = await self.neo4j_client.create_relationship(
                        from_id=subject_id,
                        to_id=object_id,
                        rel_type=rel_type,
                        properties={"confidence": relation.get("confidence", 0.8)},
                    )
                    if success:
                        stored_relations += 1

                        # 发布关系创建事件
                        if self.kafka_producer:
                            try:
                                await self.kafka_producer.publish_relation_created(
                                    relation_id=f"{subject_id}_{rel_type}_{object_id}",
                                    tenant_id="default",
                                    source_id=subject_id,
                                    target_id=object_id,
                                    relation_type=rel_type,
                                )
                            except Exception as e:
                                logger.warning(f"Failed to publish relation created event: {e}")

            result = {
                "success": True,
                "entities_extracted": len(entities),
                "entities_stored": len(entity_ids),
                "relations_extracted": len(relations),
                "relations_stored": stored_relations,
            }

            # 发布图谱构建完成事件
            if self.kafka_producer and (len(entity_ids) > 0 or stored_relations > 0):
                try:
                    await self.kafka_producer.publish_graph_built(
                        graph_id=f"graph_{hash(text[:100])}",
                        tenant_id="default",
                        entity_count=len(entity_ids),
                        relation_count=stored_relations,
                        metadata={"source": source or "unknown"}
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish graph built event: {e}")

            return result

        except Exception as e:
            logger.error(f"Extract and store failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    async def query_entity(self, entity_text: str) -> Optional[Dict[str, Any]]:
        """
        查询实体

        Args:
            entity_text: 实体文本

        Returns:
            实体信息（包含关系）
        """
        try:
            # 查找实体节点
            nodes = await self.neo4j_client.execute_query(
                """
                MATCH (n)
                WHERE n.text = $text
                RETURN n, elementId(n) as id, labels(n) as labels
                LIMIT 1
                """,
                {"text": entity_text},
            )

            if not nodes:
                return None

            node = nodes[0]
            node_id = node["id"]

            # 查找关系
            relations = await self.neo4j_client.find_relationships(node_id)

            return {
                "id": node_id,
                "labels": node["labels"],
                "properties": dict(node["n"]),
                "relations": relations,
            }

        except Exception as e:
            logger.error(f"Query entity failed: {e}")
            return None

    async def query_path(
        self, start_entity: str, end_entity: str, max_depth: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """
        查询两个实体之间的路径

        Args:
            start_entity: 起始实体
            end_entity: 目标实体
            max_depth: 最大路径深度

        Returns:
            路径列表
        """
        try:
            result = await self.neo4j_client.execute_query(
                f"""
                MATCH path = (start)-[*1..{max_depth}]-(end)
                WHERE start.text = $start AND end.text = $end
                RETURN [node in nodes(path) | {{text: node.text, labels: labels(node)}}] as nodes,
                       [rel in relationships(path) | type(rel)] as relations
                LIMIT 10
                """,
                {"start": start_entity, "end": end_entity},
            )

            paths = []
            for record in result:
                paths.append({
                    "nodes": record["nodes"],
                    "relations": record["relations"],
                })

            return paths

        except Exception as e:
            logger.error(f"Query path failed: {e}")
            return []

    async def get_neighbors(
        self, entity_text: str, max_neighbors: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取实体的邻居节点

        Args:
            entity_text: 实体文本
            max_neighbors: 最大邻居数量

        Returns:
            邻居列表
        """
        try:
            result = await self.neo4j_client.execute_query(
                f"""
                MATCH (start)-[r]-(neighbor)
                WHERE start.text = $text
                RETURN neighbor, type(r) as relation_type,
                       labels(neighbor) as labels,
                       elementId(neighbor) as id
                LIMIT {max_neighbors}
                """,
                {"text": entity_text},
            )

            neighbors = []
            for record in result:
                neighbors.append({
                    "id": record["id"],
                    "labels": record["labels"],
                    "properties": dict(record["neighbor"]),
                    "relation_type": record["relation_type"],
                })

            return neighbors

        except Exception as e:
            logger.error(f"Get neighbors failed: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息

        Returns:
            统计信息
        """
        try:
            # 节点数量
            node_count_result = await self.neo4j_client.execute_query(
                "MATCH (n) RETURN count(n) as count"
            )
            node_count = node_count_result[0]["count"] if node_count_result else 0

            # 关系数量
            rel_count_result = await self.neo4j_client.execute_query(
                "MATCH ()-[r]->() RETURN count(r) as count"
            )
            rel_count = rel_count_result[0]["count"] if rel_count_result else 0

            # 标签统计
            label_stats = await self.neo4j_client.execute_query(
                """
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
                """
            )

            return {
                "total_nodes": node_count,
                "total_relationships": rel_count,
                "label_statistics": [
                    {"label": stat["label"], "count": stat["count"]}
                    for stat in label_stats
                ],
            }

        except Exception as e:
            logger.error(f"Get statistics failed: {e}")
            return {
                "total_nodes": 0,
                "total_relationships": 0,
                "label_statistics": [],
                "error": str(e),
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态
        """
        neo4j_health = await self.neo4j_client.health_check()

        return {
            "neo4j": neo4j_health,
            "entity_extractor": {
                "healthy": self.entity_extractor.nlp is not None,
                "model": self.entity_extractor.model_name,
            },
            "relation_extractor": {
                "healthy": self.relation_extractor.nlp is not None,
                "model": self.relation_extractor.model_name,
            },
        }


# 全局实例
_kg_service: Optional[KnowledgeGraphService] = None


def get_kg_service(kafka_producer=None) -> KnowledgeGraphService:
    """
    获取知识图谱服务实例（单例）

    Args:
        kafka_producer: Kafka生产者实例（可选）

    Returns:
        KnowledgeGraphService 实例
    """
    global _kg_service

    if _kg_service is None:
        _kg_service = KnowledgeGraphService(kafka_producer=kafka_producer)
    elif kafka_producer and not _kg_service.kafka_producer:
        _kg_service.kafka_producer = kafka_producer

    return _kg_service
