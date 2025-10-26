"""Neo4j 客户端 - 知识图谱"""

import logging
from typing import Dict, List

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 图数据库客户端"""

    def __init__(
        self,
        uri: str = "bolt://neo4j:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        """初始化 Neo4j 客户端"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j client initialized: {uri}")

    async def create_node(self, label: str, properties: Dict) -> int:
        """创建节点"""
        with self.driver.session() as session:
            result = session.execute_write(
                lambda tx: tx.run(
                    f"CREATE (n:{label} $props) RETURN id(n)",
                    props=properties
                ).single()[0]
            )
            return result

    async def create_relationship(
        self, start_id: int, end_id: int, rel_type: str, properties: Dict = None
    ):
        """创建关系"""
        with self.driver.session() as session:
            query = """
            MATCH (a), (b)
            WHERE id(a) = $start_id AND id(b) = $end_id
            CREATE (a)-[r:%s $props]->(b)
            RETURN r
            """ % rel_type

            session.execute_write(
                lambda tx: tx.run(query, start_id=start_id, end_id=end_id, props=properties or {})
            )

    async def batch_create_nodes(self, nodes: List[Dict]):
        """批量创建节点"""
        with self.driver.session() as session:
            for node in nodes:
                await self.create_node(node["label"], node["properties"])

    async def batch_create_relationships(self, relationships: List[Dict]):
        """批量创建关系"""
        with self.driver.session() as session:
            for rel in relationships:
                await self.create_relationship(
                    rel["start_id"],
                    rel["end_id"],
                    rel["type"],
                    rel.get("properties"),
                )

    async def count_nodes(self) -> int:
        """统计节点数量"""
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            return result.single()["count"]

    async def count_relationships(self) -> int:
        """统计关系数量"""
        with self.driver.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            return result.single()["count"]

    async def close(self):
        """关闭连接"""
        self.driver.close()
        logger.info("Neo4j connection closed")
