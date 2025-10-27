"""
Connection Pool for Vector Databases
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConnectionPool:
    """向量数据库连接池"""

    def __init__(
        self,
        backend: str,
        host: str,
        port: int,
        min_size: int = 5,
        max_size: int = 20,
        max_idle_time: int = 300
    ):
        self.backend = backend
        self.host = host
        self.port = port
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time

        self.pool = asyncio.Queue(maxsize=max_size)
        self.size = 0
        self.created_count = 0
        self.borrowed_count = 0
        self.returned_count = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化连接池"""
        logger.info(f"Initializing connection pool: {self.backend}")

        for _ in range(self.min_size):
            conn = await self._create_connection()
            await self.pool.put(conn)

        logger.info(f"Connection pool initialized with {self.size} connections")

    async def get_connection(self) -> Any:
        """获取连接"""
        self.borrowed_count += 1

        # 尝试从池中获取
        if not self.pool.empty():
            conn = await self.pool.get()

            # 检查连接是否有效
            if await self._is_connection_valid(conn):
                logger.debug(f"Reusing connection from pool")
                return conn
            else:
                logger.warning("Connection invalid, creating new one")
                await self._close_connection(conn)
                self.size -= 1

        # 如果池为空且未达到最大值，创建新连接
        async with self._lock:
            if self.size < self.max_size:
                conn = await self._create_connection()
                return conn

        # 等待连接可用
        logger.debug("Waiting for available connection")
        conn = await self.pool.get()
        return conn

    async def return_connection(self, conn: Any):
        """归还连接"""
        self.returned_count += 1

        if conn is None:
            return

        # 检查连接是否仍然有效
        if await self._is_connection_valid(conn):
            # 如果池未满，放回池中
            if not self.pool.full():
                await self.pool.put(conn)
                logger.debug("Connection returned to pool")
            else:
                # 池已满，关闭连接
                await self._close_connection(conn)
                async with self._lock:
                    self.size -= 1
        else:
            # 连接无效，关闭
            await self._close_connection(conn)
            async with self._lock:
                self.size -= 1

    async def close_all(self):
        """关闭所有连接"""
        logger.info("Closing all connections in pool")

        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                await self._close_connection(conn)
                self.size -= 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"Connection pool closed")

    async def _create_connection(self) -> Any:
        """创建新连接"""
        async with self._lock:
            if self.size >= self.max_size:
                raise Exception("Connection pool exhausted")

            try:
                if self.backend == "milvus":
                    conn = await self._create_milvus_connection()
                elif self.backend == "qdrant":
                    conn = await self._create_qdrant_connection()
                elif self.backend == "weaviate":
                    conn = await self._create_weaviate_connection()
                else:
                    raise ValueError(f"Unsupported backend: {self.backend}")

                self.size += 1
                self.created_count += 1

                logger.info(f"Created new {self.backend} connection (total: {self.size})")
                return conn

            except Exception as e:
                logger.error(f"Failed to create connection: {e}")
                raise

    async def _create_milvus_connection(self) -> Any:
        """创建Milvus连接"""
        from pymilvus import connections

        alias = f"conn_{self.created_count}"
        connections.connect(
            alias=alias,
            host=self.host,
            port=self.port
        )

        return {"backend": "milvus", "alias": alias, "created_at": datetime.utcnow()}

    async def _create_qdrant_connection(self) -> Any:
        """创建Qdrant连接"""
        from qdrant_client import QdrantClient

        client = QdrantClient(host=self.host, port=self.port)

        return {"backend": "qdrant", "client": client, "created_at": datetime.utcnow()}

    async def _create_weaviate_connection(self) -> Any:
        """创建Weaviate连接"""
        import weaviate

        client = weaviate.Client(f"http://{self.host}:{self.port}")

        return {"backend": "weaviate", "client": client, "created_at": datetime.utcnow()}

    async def _is_connection_valid(self, conn: Any) -> bool:
        """检查连接是否有效"""
        try:
            if not conn:
                return False

            # 检查空闲时间
            created_at = conn.get("created_at")
            if created_at:
                idle_time = (datetime.utcnow() - created_at).total_seconds()
                if idle_time > self.max_idle_time:
                    return False

            # Ping连接
            if self.backend == "milvus":
                from pymilvus import utility
                utility.list_collections(using=conn.get("alias"))
            elif self.backend == "qdrant":
                client = conn.get("client")
                client.get_collections()
            elif self.backend == "weaviate":
                client = conn.get("client")
                client.is_ready()

            return True

        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            return False

    async def _close_connection(self, conn: Any):
        """关闭连接"""
        try:
            if self.backend == "milvus":
                from pymilvus import connections
                connections.disconnect(alias=conn.get("alias"))
            elif self.backend == "qdrant":
                client = conn.get("client")
                client.close()
            elif self.backend == "weaviate":
                pass  # Weaviate client auto-closes

            logger.debug(f"Connection closed: {self.backend}")

        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    def get_stats(self) -> dict:
        """获取连接池统计"""
        return {
            "backend": self.backend,
            "size": self.size,
            "available": self.pool.qsize(),
            "max_size": self.max_size,
            "created_count": self.created_count,
            "borrowed_count": self.borrowed_count,
            "returned_count": self.returned_count,
            "utilization": (self.size - self.pool.qsize()) / self.max_size if self.max_size > 0 else 0
        }
