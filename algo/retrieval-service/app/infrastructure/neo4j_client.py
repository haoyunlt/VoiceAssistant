"""Neo4j 客户端 - 知识图谱（与 Indexing Service 共享）"""

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

    async def query(self, cypher: str, parameters: Dict = None) -> List[Dict]:
        """
        执行 Cypher 查询

        Args:
            cypher: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        with self.driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    async def close(self):
        """关闭连接"""
        self.driver.close()
        logger.info("Neo4j connection closed")
