"""实体和关系抽取服务"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class Entity:
    """实体"""

    def __init__(self, text: str, entity_type: str, start: int, end: int, confidence: float = 1.0):
        self.text = text
        self.entity_type = entity_type
        self.start = start
        self.end = end
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
        }


class Relation:
    """关系"""

    def __init__(
        self, head_entity: str, relation_type: str, tail_entity: str, confidence: float = 1.0
    ):
        self.head_entity = head_entity
        self.relation_type = relation_type
        self.tail_entity = tail_entity
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {
            "head": self.head_entity,
            "relation": self.relation_type,
            "tail": self.tail_entity,
            "confidence": self.confidence,
        }


class EntityExtractionService:
    """
    实体和关系抽取服务

    支持的功能：
    1. 命名实体识别（NER）：人名、地名、组织、时间等
    2. 关系抽取：实体间的语义关系
    3. 事件抽取：事件及其参与者
    4. 知识图谱构建：将抽取结果组织为图结构
    """

    def __init__(self, llm_client):
        """
        初始化实体抽取服务

        Args:
            llm_client: LLM客户端
        """
        self.llm_client = llm_client

        # 预定义实体类型
        self.entity_types = [
            "PERSON",  # 人名
            "ORGANIZATION",  # 组织
            "LOCATION",  # 地点
            "DATE",  # 日期
            "TIME",  # 时间
            "MONEY",  # 货币
            "PERCENT",  # 百分比
            "PRODUCT",  # 产品
            "EVENT",  # 事件
            "CONCEPT",  # 概念
        ]

        # 预定义关系类型
        self.relation_types = [
            "WORKS_FOR",  # 工作于
            "LOCATED_IN",  # 位于
            "FOUNDED_BY",  # 创立者
            "CEO_OF",  # CEO
            "PART_OF",  # 部分
            "PRODUCES",  # 生产
            "OWNS",  # 拥有
            "RELATED_TO",  # 相关
        ]

    async def extract_entities(
        self, text: str, entity_types: list[str] | None = None
    ) -> list[Entity]:
        """
        抽取文本中的实体

        Args:
            text: 输入文本
            entity_types: 要抽取的实体类型（None表示全部）

        Returns:
            实体列表
        """
        logger.info(f"Extracting entities from text: {text[:100]}...")

        if entity_types is None:
            entity_types = self.entity_types

        # 使用LLM抽取实体
        entities = await self._llm_extract_entities(text, entity_types)

        logger.info(f"Extracted {len(entities)} entities")

        return entities

    async def extract_relations(
        self, text: str, entities: list[Entity] | None = None
    ) -> list[Relation]:
        """
        抽取文本中的关系

        Args:
            text: 输入文本
            entities: 已知实体（如果为None则先抽取实体）

        Returns:
            关系列表
        """
        logger.info(f"Extracting relations from text: {text[:100]}...")

        # 如果没有提供实体，先抽取
        if entities is None:
            entities = await self.extract_entities(text)

        # 使用LLM抽取关系
        relations = await self._llm_extract_relations(text, entities)

        logger.info(f"Extracted {len(relations)} relations")

        return relations

    async def extract_knowledge_graph(self, text: str) -> dict[str, Any]:
        """
        从文本构建知识图谱

        Args:
            text: 输入文本

        Returns:
            知识图谱数据
        """
        logger.info(f"Building knowledge graph from text: {text[:100]}...")

        # 1. 抽取实体
        entities = await self.extract_entities(text)

        # 2. 抽取关系
        relations = await self.extract_relations(text, entities)

        # 3. 构建图结构
        graph = {
            "nodes": [e.to_dict() for e in entities],
            "edges": [r.to_dict() for r in relations],
            "metadata": {
                "text_length": len(text),
                "entity_count": len(entities),
                "relation_count": len(relations),
            },
        }

        logger.info(f"Built knowledge graph: {len(entities)} nodes, {len(relations)} edges")

        return graph

    async def _llm_extract_entities(self, text: str, entity_types: list[str]) -> list[Entity]:
        """使用LLM抽取实体"""

        prompt = f"""Extract named entities from the following text.

Text: {text}

Entity Types to extract: {", ".join(entity_types)}

Provide the entities in JSON format:
[
  {{
    "text": "entity text",
    "type": "entity type",
    "start": start_position,
    "end": end_position
  }},
  ...
]
"""

        response = await self.llm_client.generate(prompt=prompt, temperature=0.3, max_tokens=800)

        try:
            entities_data = json.loads(response)
            entities = []

            for ent_data in entities_data:
                entity = Entity(
                    text=ent_data["text"],
                    entity_type=ent_data["type"],
                    start=ent_data.get("start", 0),
                    end=ent_data.get("end", 0),
                    confidence=ent_data.get("confidence", 0.9),
                )
                entities.append(entity)

            return entities

        except json.JSONDecodeError:
            logger.warning("Failed to parse entity extraction response")
            return []

    async def _llm_extract_relations(self, text: str, entities: list[Entity]) -> list[Relation]:
        """使用LLM抽取关系"""

        # 构建实体列表
        entity_list = "\n".join([f"- {e.text} ({e.entity_type})" for e in entities])

        prompt = f"""Extract relations between entities in the following text.

Text: {text}

Entities:
{entity_list}

Common relation types: {", ".join(self.relation_types)}

Provide the relations in JSON format:
[
  {{
    "head": "entity1",
    "relation": "relation_type",
    "tail": "entity2"
  }},
  ...
]
"""

        response = await self.llm_client.generate(prompt=prompt, temperature=0.3, max_tokens=600)

        try:
            relations_data = json.loads(response)
            relations = []

            for rel_data in relations_data:
                relation = Relation(
                    head_entity=rel_data["head"],
                    relation_type=rel_data["relation"],
                    tail_entity=rel_data["tail"],
                    confidence=rel_data.get("confidence", 0.8),
                )
                relations.append(relation)

            return relations

        except json.JSONDecodeError:
            logger.warning("Failed to parse relation extraction response")
            return []

    async def batch_extract(self, texts: list[str]) -> list[dict[str, Any]]:
        """
        批量抽取实体和关系

        Args:
            texts: 文本列表

        Returns:
            抽取结果列表
        """
        logger.info(f"Batch extracting from {len(texts)} texts")

        results = []

        for i, text in enumerate(texts):
            logger.info(f"Processing text {i + 1}/{len(texts)}")

            try:
                kg = await self.extract_knowledge_graph(text)
                results.append({"text": text, "knowledge_graph": kg, "success": True})
            except Exception as e:
                logger.error(f"Failed to extract from text {i + 1}: {e}")
                results.append({"text": text, "error": str(e), "success": False})

        return results

    def merge_knowledge_graphs(self, graphs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        合并多个知识图谱

        Args:
            graphs: 知识图谱列表

        Returns:
            合并后的知识图谱
        """
        logger.info(f"Merging {len(graphs)} knowledge graphs")

        all_nodes = []
        all_edges = []

        # 收集所有节点和边
        for graph in graphs:
            all_nodes.extend(graph.get("nodes", []))
            all_edges.extend(graph.get("edges", []))

        # 去重节点（基于文本）
        unique_nodes = {}
        for node in all_nodes:
            key = f"{node['text']}_{node['type']}"
            if key not in unique_nodes:
                unique_nodes[key] = node
            else:
                # 合并置信度（取平均）
                existing = unique_nodes[key]
                existing["confidence"] = (
                    existing.get("confidence", 1.0) + node.get("confidence", 1.0)
                ) / 2

        # 去重边
        unique_edges = {}
        for edge in all_edges:
            key = f"{edge['head']}_{edge['relation']}_{edge['tail']}"
            if key not in unique_edges:
                unique_edges[key] = edge
            else:
                # 合并置信度
                existing = unique_edges[key]
                existing["confidence"] = (
                    existing.get("confidence", 1.0) + edge.get("confidence", 1.0)
                ) / 2

        merged_graph = {
            "nodes": list(unique_nodes.values()),
            "edges": list(unique_edges.values()),
            "metadata": {
                "source_graph_count": len(graphs),
                "total_nodes": len(unique_nodes),
                "total_edges": len(unique_edges),
            },
        }

        logger.info(f"Merged graph: {len(unique_nodes)} nodes, {len(unique_edges)} edges")

        return merged_graph

    def export_to_neo4j_cypher(self, graph: dict[str, Any]) -> list[str]:
        """
        导出为Neo4j Cypher语句

        Args:
            graph: 知识图谱

        Returns:
            Cypher语句列表
        """
        cypher_statements = []

        # 创建节点
        for node in graph.get("nodes", []):
            text = node["text"].replace("'", "\\'")
            node_type = node["type"]

            cypher = f"CREATE (n:{node_type} {{name: '{text}', confidence: {node.get('confidence', 1.0)}}})"
            cypher_statements.append(cypher)

        # 创建关系
        for edge in graph.get("edges", []):
            head = edge["head"].replace("'", "\\'")
            tail = edge["tail"].replace("'", "\\'")
            relation = edge["relation"]

            cypher = f"""
MATCH (a {{name: '{head}'}}), (b {{name: '{tail}'}})
CREATE (a)-[r:{relation} {{confidence: {edge.get("confidence", 1.0)}}}]->(b)
"""
            cypher_statements.append(cypher.strip())

        return cypher_statements
