"""PostgreSQL pgvector 后端"""

import logging
import re
from typing import Any

import asyncpg
from pgvector.asyncpg import register_vector

from app.core.base_backend import VectorStoreBackend
from app.core.exceptions import VectorStoreException

logger = logging.getLogger(__name__)


class PgVectorBackend(VectorStoreBackend):
    """PostgreSQL pgvector 向量数据库后端"""

    # 允许的表名字符（防止 SQL 注入）
    VALID_TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.pool: asyncpg.Pool | None = None

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        """验证并清理表名（防止 SQL 注入）"""
        if not PgVectorBackend.VALID_TABLE_NAME_PATTERN.match(table_name):
            raise VectorStoreException(
                f"Invalid table name: {table_name}. Must match pattern: [a-zA-Z][a-zA-Z0-9_]{{0,62}}",
                backend="pgvector",
            )
        return table_name

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
        # 验证表名（防止 SQL 注入）
        safe_table_name = self._validate_table_name(collection_name)

        # 创建 pgvector 扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # 使用参数化查询创建表（使用 quote_ident 保证表名安全）
        # 注意：asyncpg 不支持表名参数化，需要手动验证和转义
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {safe_table_name} (
                id BIGSERIAL PRIMARY KEY,
                chunk_id VARCHAR(128) NOT NULL,
                document_id VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                embedding vector($1) NOT NULL,
                tenant_id VARCHAR(64) NOT NULL,
                created_at BIGINT NOT NULL,
                metadata JSONB
            )
        """, dimension)

        # 创建索引
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {safe_table_name}_embedding_idx
            ON {safe_table_name}
            USING ivfflat (embedding vector_ip_ops)
            WITH (lists = 100)
        """)

        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {safe_table_name}_tenant_idx
            ON {safe_table_name} (tenant_id)
        """)

        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS {safe_table_name}_document_idx
            ON {safe_table_name} (document_id)
        """)

        logger.info(f"Table {safe_table_name} ensured")

    async def insert_vectors(
        self,
        collection_name: str,
        data: list[dict],
    ) -> Any:
        """插入向量"""
        if not data:
            logger.warning("Empty data list for insertion")
            return None

        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

        async with self.pool.acquire() as conn:
            # 确保表存在
            dimension = len(data[0]["embedding"])
            await self._ensure_table_exists(conn, safe_table_name, dimension)

            # 批量插入
            import time
            created_at = int(time.time() * 1000)

            await conn.executemany(
                f"""
                INSERT INTO {safe_table_name}
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

        logger.info(f"Inserted {len(data)} vectors into pgvector table {safe_table_name}")

        return {"inserted": len(data)}

    async def search_vectors(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
        tenant_id: str | None = None,
        filters: str | None = None,
        search_params: dict | None = None,
    ) -> list[dict]:
        """向量检索"""
        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

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
                FROM {safe_table_name}
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
        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

        async with self.pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {safe_table_name} WHERE document_id = $1",
                document_id,
            )

        logger.info(f"Deleted vectors for document {document_id} from pgvector")

        return {"deleted": result}

    async def get_count(self, collection_name: str) -> int:
        """获取集合中的向量数量"""
        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {safe_table_name}")
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
        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

        async with self.pool.acquire() as conn:
            await self._ensure_table_exists(conn, safe_table_name, dimension)

    async def drop_collection(self, collection_name: str):
        """删除集合"""
        # 验证表名
        safe_table_name = self._validate_table_name(collection_name)

        async with self.pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {safe_table_name} CASCADE")
            logger.info(f"Dropped table {safe_table_name}")
