"""
基于Neo4j的图谱检索服务
"""

import logging
from typing import List, Optional

from app.infrastructure.neo4j_client import Neo4jClient
from app.models.retrieval import RetrievalDocument

logger = logging.getLogger(__name__)


class GraphRetrievalService:
    """基于Neo4j的图谱检索服务"""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j = neo4j_client

    async def search(
        self,
        query: str,
        top_k: int = 20,
        depth: int = 2,
        tenant_id: Optional[str] = None,
    ) -> List[RetrievalDocument]:
        """
        图谱检索

        策略:
        1. 从query中提取实体（简化：分词）
        2. 在Neo4j中查找这些实体
        3. 获取多跳相关实体和关系
        4. 聚合来源文档
        5. 按相关性排序

        Args:
            query: 查询文本
            top_k: 返回结果数
            depth: 图谱查询深度（跳数）
            tenant_id: 租户ID（保留参数，暂未使用）

        Returns:
            检索结果列表
        """
        # Step 1: 提取查询中的实体（简化实现）
        query_entities = await self._extract_entities_from_query(query)

        if not query_entities:
            logger.warning(f"未从query提取到实体: {query}")
            return []

        logger.info(f"从query提取实体: {query_entities}")

        # Step 2: 多跳关系查询
        try:
            results = await self.neo4j.multi_hop_query(
                entity_names=query_entities,
                depth=depth,
                top_k=top_k,
            )
        except Exception as e:
            logger.error(f"Neo4j多跳查询失败: {e}", exc_info=True)
            return []

        # Step 3: 转换为RetrievalDocument
        retrieval_results = []
        max_relevance = max([r["relevance"] for r in results], default=1)

        for r in results:
            # 构建metadata
            metadata = {
                "distance": r["dist"],
                "entity_path": r["entity_path"],
                "relevance": r["relevance"],
            }

            # 实体列表
            entities = r["entity_path"] if isinstance(r["entity_path"], list) else []

            # 关系列表
            relations = r.get("relations", [])

            retrieval_results.append(
                RetrievalDocument(
                    id=r["document_id"] or "unknown",
                    chunk_id=r.get("chunk_id") or f"graph_{r['document_id']}",
                    content=r["context"] or "",
                    score=r["relevance"] / max_relevance,  # 归一化到[0,1]
                    source="graph",
                    metadata=metadata,
                )
            )

        logger.info(f"Graph检索返回 {len(retrieval_results)} 条结果")
        return retrieval_results

    async def _extract_entities_from_query(self, query: str) -> List[str]:
        """
        从查询中提取实体（简化实现）

        后续可集成:
        - NER模型（SpaCy/HanLP）
        - LLM提取
        - 关键词提取

        Args:
            query: 查询文本

        Returns:
            实体名称列表
        """
        # 简化实现：分词 + Neo4j模糊匹配
        import jieba

        words = list(jieba.cut(query))

        # 过滤停用词和短词
        words = [w for w in words if len(w) >= 2]

        if not words:
            return []

        # 在Neo4j中查找匹配的实体
        cypher = """
        UNWIND $words as word
        MATCH (e:Entity)
        WHERE e.name CONTAINS word OR word CONTAINS e.name
        RETURN DISTINCT e.name as entity_name
        LIMIT 10
        """
        try:
            results = await self.neo4j.query(cypher, {"words": words})
            entity_names = [r["entity_name"] for r in results]
            return entity_names
        except Exception as e:
            logger.error(f"实体提取失败: {e}")
            # 如果Neo4j查询失败，返回原始词作为后备
            return words[:5]  # 最多返回5个词

    async def health_check(self) -> bool:
        """健康检查"""
        return await self.neo4j.health_check()
