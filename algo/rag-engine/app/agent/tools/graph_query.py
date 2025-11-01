"""
图谱查询工具 - Graph Query Tool

使用 Cypher 查询 Neo4j 知识图谱或 NetworkX 图结构。
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GraphQueryTool:
    """图谱查询工具"""

    def __init__(self, graph_store=None):
        """
        初始化图谱查询工具

        Args:
            graph_store: 图谱存储实例（GraphStore）
        """
        self.graph_store = graph_store
        self.name = "graph_query"
        self.description = (
            "在知识图谱中查询实体关系，支持多跳推理。适用于'A认识B，B认识C'类型的关系查询"
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询描述（自然语言），如'张三认识谁？'",
                },
                "entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "实体列表（可选），如['张三', '李四']",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "最大跳数（默认2）",
                    "default": 2,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行图谱查询

        Args:
            params: 包含 query, entities, max_hops

        Returns:
            {
                "text": "查询结果文本描述",
                "relationships": [...],
                "entities": [...]
            }
        """
        query = params.get("query")
        entities = params.get("entities", [])
        max_hops = params.get("max_hops", 2)

        if not query:
            raise ValueError("query 参数不能为空")

        logger.info(f"Graph query: {query[:50]}, entities={entities}, max_hops={max_hops}")

        # 检查图谱存储是否可用
        if not self.graph_store:
            return {
                "text": "图谱查询服务暂不可用，请使用向量检索",
                "relationships": [],
                "entities": [],
                "error": "graph_store_not_available",
            }

        try:
            # 方法1: 如果有实体，直接查询关系
            if entities:
                relationships = await self._query_relationships(entities, max_hops)
            else:
                # 方法2: 从查询中提取实体
                from app.graph.entity_extractor import EntityExtractor

                extractor = EntityExtractor()
                extracted_entities = await extractor.extract(query)

                if extracted_entities:
                    relationships = await self._query_relationships(extracted_entities, max_hops)
                else:
                    return {
                        "text": "未能从查询中识别出实体",
                        "relationships": [],
                        "entities": [],
                    }

            # 构建文本描述
            text = self._format_relationships(relationships) if relationships else "未找到相关关系"

            return {
                "text": text,
                "relationships": relationships,
                "entities": entities or extracted_entities,
                "count": len(relationships),
            }

        except Exception as e:
            logger.error(f"Graph query failed: {e}", exc_info=True)
            return {
                "text": f"图谱查询失败：{str(e)}",
                "relationships": [],
                "entities": entities,
                "error": str(e),
            }

    async def _query_relationships(self, entities: list, max_hops: int) -> list[dict[str, Any]]:
        """
        查询实体间的关系

        Args:
            entities: 实体列表
            max_hops: 最大跳数

        Returns:
            关系列表
        """
        relationships = []

        try:
            # 使用图谱检索器
            from app.graph.graph_retriever import GraphRetriever

            retriever = GraphRetriever(self.graph_store)

            for entity in entities:
                # 查询该实体的关系
                entity_rels = await retriever.retrieve(
                    query=entity, max_hops=max_hops, max_results=10
                )

                relationships.extend(entity_rels)

        except Exception as e:
            logger.error(f"Query relationships failed: {e}")

        return relationships

    def _format_relationships(self, relationships: list) -> str:
        """格式化关系为文本"""
        if not relationships:
            return "未找到关系"

        text_parts = [f"找到 {len(relationships)} 个关系：\n"]

        for i, rel in enumerate(relationships[:5], 1):  # 只展示前5个
            source = rel.get("source", "")
            target = rel.get("target", "")
            relation_type = rel.get("type", "相关")
            score = rel.get("score", 0)

            text_parts.append(f"{i}. {source} -{relation_type}→ {target} (置信度: {score:.2f})")

        if len(relationships) > 5:
            text_parts.append(f"\n... 还有 {len(relationships) - 5} 个关系")

        return "\n".join(text_parts)
