"""
Neo4j 异步客户端封装
"""

import logging

from neo4j import AsyncDriver, AsyncGraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j异步客户端"""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        max_connection_lifetime: int = 3600,
        max_connection_pool_size: int = 50,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver: AsyncDriver | None = None
        self.max_connection_lifetime = max_connection_lifetime
        self.max_connection_pool_size = max_connection_pool_size

    async def connect(self):
        """建立连接"""
        try:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=self.max_connection_lifetime,
                max_connection_pool_size=self.max_connection_pool_size,
            )
            # 验证连接
            await self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}, database={self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """关闭连接"""
        if self._driver:
            await self._driver.close()
            logger.info("Neo4j connection closed")

    async def query(
        self, cypher: str, parameters: dict | None = None, timeout: float = 30.0
    ) -> list[dict]:
        """
        执行Cypher查询

        Args:
            cypher: Cypher查询语句
            parameters: 查询参数
            timeout: 查询超时时间（秒）

        Returns:
            查询结果列表
        """
        if not self._driver:
            raise RuntimeError("Neo4j client not connected. Call connect() first.")

        try:
            async with self._driver.session(database=self.database) as session:
                result = await session.run(cypher, parameters or {}, timeout=timeout)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}", exc_info=True)
            raise

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        source_doc: str,
        chunk_id: str,
        properties: dict | None = None,
    ) -> str:
        """
        创建实体节点

        Args:
            name: 实体名称
            entity_type: 实体类型
            description: 实体描述
            source_doc: 来源文档ID
            chunk_id: 分块ID
            properties: 额外属性

        Returns:
            实体ID
        """
        cypher = """
        MERGE (e:Entity {name: $name})
        ON CREATE SET
            e.id = randomUUID(),
            e.type = $type,
            e.description = $description,
            e.created_at = timestamp()
        ON MATCH SET
            e.updated_at = timestamp()
        WITH e
        MERGE (d:Document {id: $source_doc})
        MERGE (e)-[:MENTIONED_IN {chunk_id: $chunk_id}]->(d)
        RETURN e.id as entity_id
        """
        params = {
            "name": name,
            "type": entity_type,
            "description": description,
            "source_doc": source_doc,
            "chunk_id": chunk_id,
        }
        if properties:
            params.update(properties)

        result = await self.query(cypher, params)
        return result[0]["entity_id"] if result else None

    async def create_relationship(
        self,
        source_name: str,
        target_name: str,
        rel_type: str,
        strength: float,
        context: str,
        source_doc: str,
    ) -> bool:
        """
        创建实体关系

        Args:
            source_name: 源实体名称
            target_name: 目标实体名称
            rel_type: 关系类型
            strength: 关系强度 (0-1)
            context: 关系上下文
            source_doc: 来源文档ID

        Returns:
            是否创建成功
        """
        cypher = """
        MATCH (a:Entity {name: $source})
        MATCH (b:Entity {name: $target})
        MERGE (a)-[r:RELATES {type: $rel_type}]->(b)
        SET r.strength = $strength,
            r.context = $context,
            r.source_doc = $source_doc,
            r.updated_at = timestamp()
        RETURN id(r) as rel_id
        """
        params = {
            "source": source_name,
            "target": target_name,
            "rel_type": rel_type,
            "strength": strength,
            "context": context,
            "source_doc": source_doc,
        }
        result = await self.query(cypher, params)
        return bool(result)

    async def get_entity_by_name(self, name: str) -> dict | None:
        """根据名称获取实体"""
        cypher = """
        MATCH (e:Entity {name: $name})
        RETURN e
        """
        result = await self.query(cypher, {"name": name})
        return result[0]["e"] if result else None

    async def get_related_entities(
        self, entity_name: str, depth: int = 2, limit: int = 50
    ) -> list[dict]:
        """
        获取相关实体（多跳关系）

        Args:
            entity_name: 实体名称
            depth: 查询深度（跳数）
            limit: 返回结果限制

        Returns:
            相关实体列表
        """
        cypher = f"""
        MATCH path = (e1:Entity {{name: $name}})-[*1..{depth}]-(e2:Entity)
        WITH e2, relationships(path) as rels, length(path) as dist
        RETURN DISTINCT
            e2.name as name,
            e2.type as type,
            e2.description as description,
            dist,
            [r in rels | {{
                type: type(r),
                strength: r.strength,
                context: r.context
            }}] as relations
        ORDER BY dist ASC, e2.name
        LIMIT $limit
        """
        result = await self.query(cypher, {"name": entity_name, "limit": limit})
        return result

    async def multi_hop_query(
        self,
        entity_names: list[str],
        depth: int = 2,
        top_k: int = 20,
    ) -> list[dict]:
        """
        多跳关系查询（用于检索）

        Args:
            entity_names: 实体名称列表
            depth: 查询深度
            top_k: 返回结果数

        Returns:
            检索结果列表
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
        WHERE document_id IS NOT NULL
        ORDER BY relevance DESC, dist ASC
        LIMIT $top_k
        RETURN document_id, context, chunk_id, entity_path, dist, relevance, relations
        """

        params = {"entity_names": entity_names, "top_k": top_k}
        return await self.query(cypher, params)

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            result = await self.query("RETURN 1 as health", timeout=5.0)
            return bool(result)
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def get_statistics(self) -> dict[str, int]:
        """获取图谱统计信息"""
        cypher = """
        MATCH (e:Entity)
        WITH count(e) as entity_count
        MATCH (d:Document)
        WITH entity_count, count(d) as doc_count
        MATCH ()-[r:RELATES]->()
        RETURN entity_count, doc_count, count(r) as relation_count
        """
        try:
            result = await self.query(cypher, timeout=10.0)
            if result:
                return {
                    "entity_count": result[0]["entity_count"],
                    "document_count": result[0]["doc_count"],
                    "relation_count": result[0]["relation_count"],
                }
            return {"entity_count": 0, "document_count": 0, "relation_count": 0}
        except Exception as e:
            logger.error(f"Failed to get Neo4j statistics: {e}")
            return {"entity_count": 0, "document_count": 0, "relation_count": 0}
