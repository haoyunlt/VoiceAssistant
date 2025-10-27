"""
Neo4j 图数据库客户端
用于存储和查询知识图谱
"""

import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 客户端"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "voiceassistant",
        database: str = "neo4j"
    ):
        """
        初始化 Neo4j 客户端

        Args:
            uri: Neo4j 服务地址
            user: 用户名
            password: 密码
            database: 数据库名称
        """
        self.uri = uri
        self.database = database

        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            logger.info(f"Neo4j client initialized: {uri}/{database}")
        except Neo4jError as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def create_entity(
        self,
        entity: Dict[str, Any],
        document_id: str,
        tenant_id: str
    ) -> str:
        """
        创建实体节点

        Args:
            entity: 实体字典
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            节点 ID
        """
        query = """
        MERGE (e:Entity {text: $text, label: $label, tenant_id: $tenant_id})
        ON CREATE SET
            e.created_at = datetime(),
            e.document_id = $document_id,
            e.confidence = $confidence
        ON MATCH SET
            e.updated_at = datetime(),
            e.document_id = $document_id
        RETURN elementId(e) as node_id
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(
                query,
                text=entity["text"],
                label=entity["label"],
                tenant_id=tenant_id,
                document_id=document_id,
                confidence=entity.get("confidence", 1.0)
            )
            record = result.single()
            return record["node_id"] if record else None

    def create_relation(
        self,
        relation: Dict[str, Any],
        document_id: str,
        tenant_id: str
    ) -> bool:
        """
        创建关系

        Args:
            relation: 关系字典
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            是否成功
        """
        # 动态构建关系类型（Neo4j 要求关系类型大写）
        relation_type = relation["relation"].upper().replace(" ", "_")

        query = f"""
        MATCH (source:Entity {{text: $source, tenant_id: $tenant_id}})
        MATCH (target:Entity {{text: $target, tenant_id: $tenant_id}})
        MERGE (source)-[r:{relation_type}]->(target)
        ON CREATE SET
            r.created_at = datetime(),
            r.document_id = $document_id,
            r.confidence = $confidence,
            r.method = $method
        ON MATCH SET
            r.updated_at = datetime()
        RETURN elementId(r) as rel_id
        """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(
                    query,
                    source=relation["source"],
                    target=relation["target"],
                    tenant_id=tenant_id,
                    document_id=document_id,
                    confidence=relation.get("confidence", 1.0),
                    method=relation.get("method", "unknown")
                )
                record = result.single()
                return record is not None
        except Neo4jError as e:
            logger.error(f"Failed to create relation: {e}")
            return False

    def bulk_create_graph(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        document_id: str,
        tenant_id: str
    ) -> Dict[str, int]:
        """
        批量创建图谱

        Args:
            entities: 实体列表
            relations: 关系列表
            document_id: 文档 ID
            tenant_id: 租户 ID

        Returns:
            统计信息 {entities_created, relations_created}
        """
        logger.info(f"Creating graph: {len(entities)} entities, {len(relations)} relations")

        entities_created = 0
        relations_created = 0

        # 创建实体
        for entity in entities:
            node_id = self.create_entity(entity, document_id, tenant_id)
            if node_id:
                entities_created += 1

        # 创建关系
        for relation in relations:
            if self.create_relation(relation, document_id, tenant_id):
                relations_created += 1

        logger.info(
            f"Graph created: {entities_created}/{len(entities)} entities, "
            f"{relations_created}/{len(relations)} relations"
        )

        return {
            "entities_created": entities_created,
            "relations_created": relations_created
        }

    def find_entity(
        self,
        text: str,
        tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        查找实体

        Args:
            text: 实体文本
            tenant_id: 租户 ID

        Returns:
            实体信息，不存在返回 None
        """
        query = """
        MATCH (e:Entity {text: $text, tenant_id: $tenant_id})
        RETURN e.text as text, e.label as label, e.confidence as confidence
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, text=text, tenant_id=tenant_id)
            record = result.single()
            if record:
                return dict(record)
            return None

    def find_relations(
        self,
        entity_text: str,
        tenant_id: str,
        direction: str = "outgoing"
    ) -> List[Dict[str, Any]]:
        """
        查找实体的关系

        Args:
            entity_text: 实体文本
            tenant_id: 租户 ID
            direction: 方向 (outgoing, incoming, both)

        Returns:
            关系列表
        """
        if direction == "outgoing":
            query = """
            MATCH (source:Entity {text: $text, tenant_id: $tenant_id})-[r]->(target:Entity)
            RETURN source.text as source, type(r) as relation, target.text as target,
                   r.confidence as confidence
            """
        elif direction == "incoming":
            query = """
            MATCH (source:Entity)-[r]->(target:Entity {text: $text, tenant_id: $tenant_id})
            RETURN source.text as source, type(r) as relation, target.text as target,
                   r.confidence as confidence
            """
        else:  # both
            query = """
            MATCH (e:Entity {text: $text, tenant_id: $tenant_id})-[r]-(other:Entity)
            RETURN e.text as entity, type(r) as relation, other.text as other,
                   r.confidence as confidence
            """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, text=entity_text, tenant_id=tenant_id)
            return [dict(record) for record in result]

    def delete_document_nodes(self, document_id: str) -> int:
        """
        删除文档相关的所有节点和关系

        Args:
            document_id: 文档 ID

        Returns:
            删除的节点数量
        """
        query = """
        MATCH (n {document_id: $document_id})
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, document_id=document_id)
            record = result.single()
            deleted_count = record["deleted_count"] if record else 0

            logger.info(f"Deleted {deleted_count} nodes for document {document_id}")
            return deleted_count

    def community_detection(
        self,
        tenant_id: str,
        algorithm: str = "louvain"
    ) -> Dict[str, List[str]]:
        """
        执行社区检测

        Args:
            tenant_id: 租户 ID
            algorithm: 算法 (louvain, label_propagation)

        Returns:
            社区字典
        """
        # 需要 Neo4j Graph Data Science (GDS) 插件
        if algorithm == "louvain":
            query = """
            CALL gds.louvain.stream({
                nodeQuery: 'MATCH (e:Entity {tenant_id: $tenant_id}) RETURN id(e) AS id',
                relationshipQuery: 'MATCH (e1:Entity {tenant_id: $tenant_id})-[r]-(e2:Entity {tenant_id: $tenant_id}) RETURN id(e1) AS source, id(e2) AS target'
            })
            YIELD nodeId, communityId
            MATCH (e) WHERE id(e) = nodeId
            RETURN communityId, collect(e.text) as members
            """
        else:
            logger.warning(f"Algorithm {algorithm} not implemented, using simple query")
            # 简单版本：基于连通分量
            query = """
            MATCH (e:Entity {tenant_id: $tenant_id})
            RETURN 'community_0' as communityId, collect(e.text) as members
            """

        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, tenant_id=tenant_id)
                communities = {}
                for record in result:
                    community_id = f"community_{record['communityId']}"
                    communities[community_id] = record["members"]

                logger.info(f"Detected {len(communities)} communities for tenant {tenant_id}")
                return communities
        except Neo4jError as e:
            logger.error(f"Community detection failed: {e}")
            return {}

    def get_graph_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        获取图谱统计信息

        Args:
            tenant_id: 租户 ID

        Returns:
            统计信息
        """
        query = """
        MATCH (e:Entity {tenant_id: $tenant_id})
        OPTIONAL MATCH (e)-[r]-()
        RETURN
            count(DISTINCT e) as entity_count,
            count(DISTINCT r) as relation_count,
            collect(DISTINCT labels(e)) as entity_labels
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query, tenant_id=tenant_id)
            record = result.single()
            if record:
                return {
                    "entity_count": record["entity_count"],
                    "relation_count": record["relation_count"] // 2,  # 无向图
                    "entity_labels": record["entity_labels"]
                }
            return {"entity_count": 0, "relation_count": 0, "entity_labels": []}

    def execute_cypher(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        """
        执行自定义 Cypher 查询

        Args:
            query: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Neo4jError as e:
            logger.error(f"Cypher query failed: {e}")
            return []
