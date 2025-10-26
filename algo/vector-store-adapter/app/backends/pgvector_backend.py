"""PostgreSQL pgvector 后端"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg
from pgvector.asyncpg import register_vector

from app.core.base_backend import VectorStoreBackend

logger = logging.getLogger(__name__)


class PgVectorBackend(VectorStoreBackend):
    """PostgreSQL pgvector 向量数据库后端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """初始化 PostgreSQL 连接池"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
                min_size=2,
                max_size=10,
            )

            # 注册 vector 类型
            async with self.pool.acquire() as conn:
                await register_vector(conn)

            self.initialized = True
            logger.info(f"Connected to PostgreSQL at {self.config['host']}:{self.config['port']}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        if self.pool:
            await self.pool.close()
            self.initialized = False
            logger.info("Disconnected from PostgreSQL")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self.pool:
            return False

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    async def _ensure_table_exists(self, conn: asyncpg.Connection, collection_name: str, dimension: int):
        """确保表存在"""
        # 创建 pgvector 扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # 创建表
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {collection_name} (
                id BIGSERIAL PRIMARY KEY,
                chunk_id VARCHAR(128) NOT NULL,
                document_id VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                embedding vector({dimension}) NOT NULL,
                tenant_id VARCHAR(64) NOT NULL,
                created_at BIGINT NOT NULL,
                metadata JSONB
            )
        """)

        # 创建索引
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx
            ON {collection_name}
            USING ivfflat (embedding vector_ip_ops)
            WITH (lists = 100)
        """)

        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {collection_name}_tenant_idx
            ON {collection_name} (tenant_id)
        """)

        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {collection_name}_document_idx
            ON {collection_name} (document_id)
        """)

        logger.info(f"Table {collection_name} ensured")

    async def insert_vectors(
        self,
        collection_name: str,
        data: List[Dict],
    ) -> Any:
        """插入向量"""
        if not data:
            logger.warning("Empty data list for insertion")
            return None

        async with self.pool.acquire() as conn:
            # 确保表存在
            dimension = len(data[0]["embedding"])
            await self._ensure_table_exists(conn, collection_name, dimension)

            # 批量插入
            import time
            created_at = int(time.time() * 1000)

            await conn.executemany(
                f"""
                INSERT INTO {collection_name}
                (chunk_id, document_id, content, embedding, tenant_id, created_at, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                [
                    (
                        item["chunk_id"],
                        item["document_id"],
                        item["content"],
                        item["embedding"],
                        item.get("tenant_id", "default"),
                        created_at,
                        item.get("metadata"),
                    )
                    for item in data
                ],
            )

        logger.info(f"Inserted {len(data)} vectors into pgvector table {collection_name}")

        return {"inserted": len(data)}

    async def search_vectors(
        self,
        collection_name: str,
        query_vector: List[float],
        top_k: int = 10,
        tenant_id: Optional[str] = None,
        filters: Optional[str] = None,
        search_params: Optional[Dict] = None,
    ) -> List[Dict]:
        """向量检索"""
        async with self.pool.acquire() as conn:
            # 构建 WHERE 子句
            where_clauses = []
            params = [query_vector, top_k]
            param_idx = 3

            if tenant_id:
                where_clauses.append(f"tenant_id = ${param_idx}")
                params.append(tenant_id)
                param_idx += 1

            where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # 执行搜索（使用内积）
            query = f"""
                SELECT
                    chunk_id,
                    document_id,
                    content,
                    tenant_id,
                    1 - (embedding <#> $1) as score
                FROM {collection_name}
                {where_str}
                ORDER BY embedding <#> $1
                LIMIT $2
            """

            rows = await conn.fetch(query, *params)

            # 转换结果
            output = []
            for row in rows:
                output.append({
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                    "tenant_id": row["tenant_id"],
                    "score": float(row["score"]),
                    "backend": "pgvector",
                })

            logger.info(f"pgvector search returned {len(output)} results")

            return output

    async def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> Any:
        """删除文档的所有向量"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {collection_name} WHERE document_id = $1",
                document_id,
            )

        logger.info(f"Deleted vectors for document {document_id} from pgvector")

        return {"deleted": result}

    async def get_count(self, collection_name: str) -> int:
        """获取集合中的向量数量"""
        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {collection_name}")
                return count
        except Exception:
            return 0

    async def create_collection(
        self,
        collection_name: str,
        dimension: int,
        **kwargs,
    ):
        """创建集合"""
        async with self.pool.acquire() as conn:
            await self._ensure_table_exists(conn, collection_name, dimension)

    async def drop_collection(self, collection_name: str):
        """删除集合"""
        async with self.pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {collection_name} CASCADE")
            logger.info(f"Dropped table {collection_name}")
