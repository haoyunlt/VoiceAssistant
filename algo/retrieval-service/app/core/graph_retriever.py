"""图谱检索器 - 基于 Neo4j（增强版 - 多跳关系查询）"""

import logging
import time
from typing import Dict, List, Optional

import jieba

from app.infrastructure.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphRetriever:
    """图谱检索器（增强版）"""

    def __init__(
        self,
        uri: str = "bolt://neo4j:7687",
        user: str = "neo4j",
        password: str = "password",
        default_depth: int = 2,
    ):
        """初始化图谱检索器"""
        self.neo4j_client = None
        self.uri = uri
        self.user = user
        self.password = password
        self.default_depth = default_depth
        logger.info("Graph retriever created")

    async def initialize(self):
        """初始化组件"""
        # 初始化 Neo4j 客户端
        self.neo4j_client = Neo4jClient(
            uri=self.uri,
            user=self.user,
            password=self.password,
        )
        await self.neo4j_client.connect()

        # 创建索引
        await self.neo4j_client.create_indexes()

        logger.info("Graph retriever initialized")

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        depth: int = None,
        tenant_id: str = None,
        filters: Dict = None,
    ) -> List[Dict]:
        """
        图谱检索（多跳关系）

        策略:
        1. 从query中提取实体（简化：分词+模糊匹配）
        2. 在Neo4j中查找这些实体
        3. 获取多跳相关实体和关系
        4. 聚合来源文档
        5. 按相关性排序

        Args:
            query: 查询文本
            top_k: 返回结果数
            depth: 跳数（1-3）
            tenant_id: 租户 ID
            filters: 过滤条件

        Returns:
            检索结果列表，格式:
            {
                "document_id": str,
                "chunk_id": str,
                "text": str,
                "score": float,
                "source": "graph",
                "metadata": dict,
                "entities": list,
                "relations": list
            }
        """
        start_time = time.time()

        # 从查询中提取实体
        query_entities = await self._extract_entities(query)

        if not query_entities:
            logger.info(f"No entities extracted from query: {query}")
            return []

        logger.info(f"Extracted entities: {query_entities}")

        # 多跳关系查询
        depth = depth or self.default_depth
        results = await self._multi_hop_search(
            query_entities,
            depth=depth,
            top_k=top_k,
            tenant_id=tenant_id,
        )

        elapsed = time.time() - start_time
        logger.info(
            f"Graph retrieval: found {len(results)} results in {elapsed:.3f}s "
            f"(entities={query_entities}, depth={depth})"
        )

        return results

    async def _extract_entities(self, query: str) -> List[str]:
        """
        从查询中提取实体（集成 NER 模型）

        策略:
        1. 使用 NER 模型提取实体
        2. 在Neo4j中匹配已有实体
        3. 后备：使用分词

        支持的 NER 后端: SpaCy, HanLP, Jieba
        """
        entity_names = []

        # 尝试使用 NER 服务
        try:
            from app.services.ner_service import get_ner_service

            ner_service = await get_ner_service(backend="jieba", language="zh")
            extracted_entities = await ner_service.extract_entity_names(query, min_length=2)

            if extracted_entities:
                logger.info(f"NER extracted entities: {extracted_entities}")

                # 在 Neo4j 中验证这些实体
                for entity_text in extracted_entities:
                    matches = await self.neo4j_client.search_entities_by_pattern(
                        pattern=entity_text,
                        limit=3
                    )
                    entity_names.extend([m["name"] for m in matches])

                if entity_names:
                    # 去重
                    entity_names = list(set(entity_names))
                    return entity_names[:10]

        except Exception as e:
            logger.warning(f"NER service failed, falling back to jieba: {e}")

        # 后备方案：使用分词
        words = list(jieba.cut(query))
        words = [w for w in words if len(w) >= 2]

        if not words:
            return []

        # 在Neo4j中查找匹配的实体
        for word in words:
            matches = await self.neo4j_client.search_entities_by_pattern(
                pattern=word,
                limit=5
            )
            entity_names.extend([m["name"] for m in matches])

        # 去重
        entity_names = list(set(entity_names))

        return entity_names[:10]  # 最多10个实体

    async def _multi_hop_search(
        self,
        entity_names: List[str],
        depth: int,
        top_k: int,
        tenant_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        多跳关系搜索

        Cypher查询：
        1. 从给定实体出发
        2. 沿关系走1-N跳
        3. 收集路径中的所有关系
        4. 聚合到来源文档
        5. 按相关度排序
        """
        cypher = f"""
        MATCH path = (e1:Entity)-[*1..{depth}]-(e2:Entity)
        WHERE e1.name IN $entity_names
        WITH
            path,
            relationships(path) as rels,
            length(path) as dist,
            [n in nodes(path) | n.name] as entity_path
        UNWIND rels as rel
        WITH DISTINCT
            rel.source_doc as document_id,
            rel.context as context,
            rel.chunk_id as chunk_id,
            entity_path,
            dist,
            COUNT(*) as relevance,
            COLLECT(DISTINCT {{
                source: startNode(rel).name,
                target: endNode(rel).name,
                type: type(rel),
                strength: rel.strength
            }}) as relations
        WHERE document_id IS NOT NULL AND document_id <> ''
        RETURN
            document_id,
            context,
            chunk_id,
            entity_path,
            dist,
            relevance,
            relations
        ORDER BY relevance DESC, dist ASC
        LIMIT $top_k
        """

        params = {
            "entity_names": entity_names,
            "top_k": top_k,
        }

        try:
            raw_results = await self.neo4j_client.query(cypher, params)
        except Exception as e:
            logger.error(f"Graph query failed: {e}", exc_info=True)
            return []

        if not raw_results:
            return []

        # 转换为标准格式
        results = []
        max_relevance = max([r["relevance"] for r in raw_results], default=1)

        for r in raw_results:
            results.append({
                "document_id": r.get("document_id", "unknown"),
                "chunk_id": r.get("chunk_id", f"graph_{r.get('document_id', 'unknown')}"),
                "text": r.get("context", ""),
                "score": float(r["relevance"]) / max_relevance,  # 归一化到[0,1]
                "source": "graph",
                "metadata": {
                    "distance": r.get("dist", 0),
                    "entity_path": r.get("entity_path", []),
                    "relevance": r.get("relevance", 0),
                },
                "entities": r.get("entity_path", []),
                "relations": r.get("relations", []),
            })

        return results

    async def get_stats(self) -> Dict:
        """获取图谱统计信息"""
        if not self.neo4j_client:
            return {}

        stats = await self.neo4j_client.get_graph_stats()
        return stats

    async def cleanup(self):
        """清理资源"""
        if self.neo4j_client:
            await self.neo4j_client.close()
        logger.info("Graph retriever cleaned up")
