"""
Neo4j Client - Neo4j 图数据库客户端

提供 Neo4j 连接和基础图操作
"""

from typing import Any

try:
    from neo4j import AsyncGraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None

import logging

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 客户端"""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        max_connection_lifetime: int = 3600,
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        max_transaction_retry_time: int = 30,
    ):
        """
        初始化 Neo4j 客户端

        Args:
            uri: Neo4j 连接 URI
            user: 用户名
            password: 密码
            max_connection_lifetime: 最大连接生命周期（秒）
            max_connection_pool_size: 最大连接池大小
            connection_timeout: 连接超时（秒）
            max_transaction_retry_time: 最大事务重试时间（秒）
        """
        if not NEO4J_AVAILABLE:
            logger.warning("neo4j driver not installed. Install with: pip install neo4j")
            self.driver = None
        else:
            try:
                self.driver = AsyncGraphDatabase.driver(
                    uri,
                    auth=(user, password),
                    max_connection_lifetime=max_connection_lifetime,
                    max_connection_pool_size=max_connection_pool_size,
                    connection_timeout=connection_timeout,
                    max_transaction_retry_time=max_transaction_retry_time,
                )
                logger.info(
                    f"Neo4j client initialized: {uri} (pool_size={max_connection_pool_size})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j: {e}")
                self.driver = None

    async def close(self):
        """关闭连接"""
        if self.driver:
            await self.driver.close()

    async def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        执行 Cypher 查询

        Args:
            query: Cypher 查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        if not self.driver:
            logger.warning("Neo4j driver not available")
            return []

        try:
            async with self.driver.session() as session:
                result = await session.run(query, parameters or {})
                records = await result.data()
                return records

        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return []

    # 别名方法，保持向后兼容
    async def query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """执行 Cypher 查询（别名方法）"""
        return await self.execute_query(query, parameters)

    async def create_node(self, label: str, properties: dict[str, Any]) -> str | None:
        """
        创建节点

        Args:
            label: 节点标签
            properties: 节点属性

        Returns:
            节点 ID
        """
        query = f"""
        CREATE (n:{label} $props)
        RETURN elementId(n) as id
        """

        try:
            result = await self.execute_query(query, {"props": properties})
            if result:
                return result[0].get("id")
            return None

        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            return None

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> bool:
        """
        创建关系

        Args:
            from_id: 起始节点 ID
            to_id: 目标节点 ID
            rel_type: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        query = f"""
        MATCH (a), (b)
        WHERE elementId(a) = $from_id AND elementId(b) = $to_id
        CREATE (a)-[r:{rel_type} $props]->(b)
        RETURN r
        """

        try:
            result = await self.execute_query(
                query, {"from_id": from_id, "to_id": to_id, "props": properties or {}}
            )
            return len(result) > 0

        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    async def find_nodes(
        self, label: str, properties: dict[str, Any] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        查找节点

        Args:
            label: 节点标签
            properties: 匹配属性
            limit: 结果数量限制

        Returns:
            节点列表
        """
        where_clause = ""
        if properties:
            conditions = [f"n.{key} = ${key}" for key in properties]
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        MATCH (n:{label})
        {where_clause}
        RETURN n, elementId(n) as id
        LIMIT {limit}
        """

        try:
            result = await self.execute_query(query, properties or {})
            return [{"id": record["id"], **dict(record["n"])} for record in result]

        except Exception as e:
            logger.error(f"Failed to find nodes: {e}")
            return []

    async def find_relationships(
        self, from_id: str, rel_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        查找关系

        Args:
            from_id: 起始节点 ID
            rel_type: 关系类型（可选）
            limit: 结果数量限制

        Returns:
            关系列表
        """
        rel_pattern = f"[r:{rel_type}]" if rel_type else "[r]"

        query = f"""
        MATCH (a)-{rel_pattern}->(b)
        WHERE elementId(a) = $from_id
        RETURN type(r) as type, properties(r) as props,
               elementId(b) as target_id, labels(b) as target_labels, properties(b) as target_props
        LIMIT {limit}
        """

        try:
            result = await self.execute_query(query, {"from_id": from_id})
            return [
                {
                    "type": record["type"],
                    "properties": dict(record["props"]) if record["props"] else {},
                    "target": {
                        "id": record["target_id"],
                        "labels": record["target_labels"],
                        "properties": dict(record["target_props"])
                        if record["target_props"]
                        else {},
                    },
                }
                for record in result
            ]

        except Exception as e:
            logger.error(f"Failed to find relationships: {e}")
            return []

    async def health_check(self) -> dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态
        """
        if not NEO4J_AVAILABLE:
            return {
                "healthy": False,
                "error": "neo4j driver not installed",
            }

        if not self.driver:
            return {
                "healthy": False,
                "error": "Neo4j driver not initialized",
            }

        try:
            # 尝试执行简单查询
            result = await self.execute_query("RETURN 1 as test")
            if result and result[0].get("test") == 1:
                return {
                    "healthy": True,
                    "connected": True,
                }
            else:
                return {
                    "healthy": False,
                    "error": "Query execution failed",
                }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


# 全局实例
_neo4j_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """
    获取 Neo4j 客户端实例（单例）

    Returns:
        Neo4jClient 实例
    """
    global _neo4j_client

    if _neo4j_client is None:
        from app.core.config import settings

        _neo4j_client = Neo4jClient(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
            max_connection_lifetime=settings.NEO4J_MAX_CONNECTION_LIFETIME,
            max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
            connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
            max_transaction_retry_time=settings.NEO4J_MAX_TRANSACTION_RETRY_TIME,
        )

    return _neo4j_client
