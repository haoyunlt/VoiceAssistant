"""
Temporal Graph Service - 时序图谱服务

支持时间维度的知识图谱，追踪实体和关系的时间演化
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class TemporalGraphService:
    """时序图谱服务"""

    def __init__(self, neo4j_client):
        """
        初始化时序图谱服务

        Args:
            neo4j_client: Neo4j客户端
        """
        self.neo4j = neo4j_client

    async def create_temporal_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        valid_from: datetime | str,
        valid_to: datetime | str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """
        创建时序关系

        Args:
            from_id: 源实体ID
            to_id: 目标实体ID
            rel_type: 关系类型
            valid_from: 生效开始时间
            valid_to: 生效结束时间（None表示持续有效）
            properties: 关系属性

        Returns:
            是否成功
        """
        try:
            properties = properties or {}

            # 转换时间格式
            if isinstance(valid_from, datetime):
                valid_from = valid_from.isoformat()
            if isinstance(valid_to, datetime):
                valid_to = valid_to.isoformat()

            # 添加时间属性
            properties["valid_from"] = valid_from
            if valid_to:
                properties["valid_to"] = valid_to

            # 创建关系
            query = f"""
            MATCH (from), (to)
            WHERE elementId(from) = $from_id AND elementId(to) = $to_id
            MERGE (from)-[r:{rel_type}]->(to)
            SET r += $properties
            RETURN elementId(r) as rel_id
            """

            result = await self.neo4j.execute_query(
                query,
                {"from_id": from_id, "to_id": to_id, "properties": properties},
            )

            if result:
                logger.info(
                    f"Created temporal relationship: {from_id} -[{rel_type}]-> {to_id} "
                    f"(valid_from={valid_from}, valid_to={valid_to})"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to create temporal relationship: {e}")
            return False

    async def query_entity_at_time(
        self, entity_text: str, timestamp: datetime | str, max_depth: int = 1
    ) -> dict[str, Any]:
        """
        查询指定时间点的实体及其关系

        Args:
            entity_text: 实体文本
            timestamp: 查询时间点
            max_depth: 关系深度

        Returns:
            实体信息及时序关系
        """
        try:
            # 转换时间格式
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()

            # 查询实体
            entity_query = """
            MATCH (n:Entity)
            WHERE n.text = $text
            RETURN elementId(n) as id, n.text as text, labels(n) as labels,
                   n.created_at as created_at, n.updated_at as updated_at
            LIMIT 1
            """

            entity_result = await self.neo4j.execute_query(
                entity_query, {"text": entity_text}
            )

            if not entity_result:
                return {"found": False}

            entity = entity_result[0]
            entity_id = entity["id"]

            # 查询时序关系
            relations_query = f"""
            MATCH (n)-[r]->(m)
            WHERE elementId(n) = $entity_id
              AND r.valid_from <= $timestamp
              AND (r.valid_to IS NULL OR r.valid_to >= $timestamp)
            RETURN type(r) as rel_type,
                   r.valid_from as valid_from,
                   r.valid_to as valid_to,
                   properties(r) as properties,
                   m.text as target_text,
                   labels(m) as target_labels,
                   elementId(m) as target_id
            LIMIT 100
            """

            relations_result = await self.neo4j.execute_query(
                relations_query, {"entity_id": entity_id, "timestamp": timestamp}
            )

            relations = []
            for r in relations_result:
                relations.append(
                    {
                        "type": r["rel_type"],
                        "target": {
                            "id": r["target_id"],
                            "text": r["target_text"],
                            "labels": r["target_labels"],
                        },
                        "valid_from": r["valid_from"],
                        "valid_to": r["valid_to"],
                        "properties": r["properties"],
                    }
                )

            return {
                "found": True,
                "entity": {
                    "id": entity["id"],
                    "text": entity["text"],
                    "labels": entity["labels"],
                },
                "timestamp": timestamp,
                "relations": relations,
                "relations_count": len(relations),
            }

        except Exception as e:
            logger.error(f"Failed to query entity at time: {e}")
            return {"found": False, "error": str(e)}

    async def query_temporal_path(
        self,
        start_entity: str,
        end_entity: str,
        timestamp: datetime | str,
        max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """
        查询指定时间点两个实体间的路径

        Args:
            start_entity: 起始实体
            end_entity: 目标实体
            timestamp: 查询时间点
            max_depth: 最大路径深度

        Returns:
            时序路径列表
        """
        try:
            # 转换时间格式
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()

            query = f"""
            MATCH path = (start:Entity)-[rels*1..{max_depth}]->(end:Entity)
            WHERE start.text = $start
              AND end.text = $end
              AND ALL(r IN rels WHERE
                r.valid_from <= $timestamp AND
                (r.valid_to IS NULL OR r.valid_to >= $timestamp)
              )
            RETURN [node IN nodes(path) | {{
                text: node.text,
                labels: labels(node)
            }}] as nodes,
            [rel IN rels | {{
                type: type(rel),
                valid_from: rel.valid_from,
                valid_to: rel.valid_to
            }}] as relations
            LIMIT 10
            """

            results = await self.neo4j.execute_query(
                query,
                {"start": start_entity, "end": end_entity, "timestamp": timestamp},
            )

            paths = []
            for record in results:
                paths.append(
                    {
                        "nodes": record["nodes"],
                        "relations": record["relations"],
                        "length": len(record["relations"]),
                        "timestamp": timestamp,
                    }
                )

            logger.info(
                f"Found {len(paths)} temporal paths from '{start_entity}' to '{end_entity}' at {timestamp}"
            )

            return paths

        except Exception as e:
            logger.error(f"Failed to query temporal path: {e}")
            return []

    async def get_entity_history(
        self, entity_text: str, start_time: datetime | str | None = None, end_time: datetime | str | None = None
    ) -> list[dict[str, Any]]:
        """
        获取实体的历史变化

        Args:
            entity_text: 实体文本
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            历史事件列表
        """
        try:
            # 转换时间格式
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat()

            # 构建时间过滤条件
            time_filter = ""
            params = {"text": entity_text}

            if start_time:
                time_filter += " AND r.valid_from >= $start_time"
                params["start_time"] = start_time

            if end_time:
                time_filter += " AND r.valid_from <= $end_time"
                params["end_time"] = end_time

            query = f"""
            MATCH (n:Entity {{text: $text}})-[r]->(m)
            WHERE r.valid_from IS NOT NULL {time_filter}
            RETURN type(r) as rel_type,
                   r.valid_from as valid_from,
                   r.valid_to as valid_to,
                   m.text as target_text,
                   labels(m) as target_labels,
                   properties(r) as properties
            ORDER BY r.valid_from ASC
            """

            results = await self.neo4j.execute_query(query, params)

            history = []
            for r in results:
                history.append(
                    {
                        "event_type": "relationship_created",
                        "relation_type": r["rel_type"],
                        "target": {
                            "text": r["target_text"],
                            "labels": r["target_labels"],
                        },
                        "valid_from": r["valid_from"],
                        "valid_to": r["valid_to"],
                        "properties": r["properties"],
                    }
                )

            logger.info(f"Found {len(history)} history events for entity '{entity_text}'")

            return history

        except Exception as e:
            logger.error(f"Failed to get entity history: {e}")
            return []

    async def update_relationship_validity(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        new_valid_to: datetime | str,
    ) -> bool:
        """
        更新关系的有效期

        Args:
            from_id: 源实体ID
            to_id: 目标实体ID
            rel_type: 关系类型
            new_valid_to: 新的结束时间

        Returns:
            是否成功
        """
        try:
            if isinstance(new_valid_to, datetime):
                new_valid_to = new_valid_to.isoformat()

            query = f"""
            MATCH (from)-[r:{rel_type}]->(to)
            WHERE elementId(from) = $from_id AND elementId(to) = $to_id
            SET r.valid_to = $valid_to,
                r.updated_at = datetime()
            RETURN elementId(r) as rel_id
            """

            result = await self.neo4j.execute_query(
                query, {"from_id": from_id, "to_id": to_id, "valid_to": new_valid_to}
            )

            if result:
                logger.info(
                    f"Updated relationship validity: {from_id} -[{rel_type}]-> {to_id}, "
                    f"valid_to={new_valid_to}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to update relationship validity: {e}")
            return False

    async def get_temporal_statistics(
        self, document_id: str | None = None
    ) -> dict[str, Any]:
        """
        获取时序图谱统计信息

        Args:
            document_id: 文档ID（可选）

        Returns:
            统计信息
        """
        try:
            # 构建过滤条件
            where_clause = ""
            params = {}

            if document_id:
                where_clause = "WHERE n.document_id = $document_id"
                params["document_id"] = document_id

            # 统计时序关系数量
            query = f"""
            MATCH (n:Entity {where_clause})-[r]->()
            WHERE r.valid_from IS NOT NULL
            WITH r,
                 CASE WHEN r.valid_to IS NULL THEN true ELSE false END as is_active
            RETURN count(r) as total_temporal_relations,
                   sum(CASE WHEN is_active THEN 1 ELSE 0 END) as active_relations,
                   sum(CASE WHEN is_active THEN 0 ELSE 1 END) as expired_relations
            """

            result = await self.neo4j.execute_query(query, params)

            if result:
                stats = result[0]
                return {
                    "total_temporal_relations": stats["total_temporal_relations"],
                    "active_relations": stats["active_relations"],
                    "expired_relations": stats["expired_relations"],
                }

            return {
                "total_temporal_relations": 0,
                "active_relations": 0,
                "expired_relations": 0,
            }

        except Exception as e:
            logger.error(f"Failed to get temporal statistics: {e}")
            return {}


# 全局实例
_temporal_graph_service: TemporalGraphService | None = None


def get_temporal_graph_service(neo4j_client) -> TemporalGraphService:
    """
    获取时序图谱服务实例（单例）

    Args:
        neo4j_client: Neo4j客户端

    Returns:
        TemporalGraphService实例
    """
    global _temporal_graph_service

    if _temporal_graph_service is None:
        _temporal_graph_service = TemporalGraphService(neo4j_client)

    return _temporal_graph_service
