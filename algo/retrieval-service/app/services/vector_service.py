"""
Vector search service using Milvus
"""

import logging
import time
from typing import Any

from pymilvus import Collection, connections

from app.core.config import settings
from app.models.retrieval import RetrievalDocument

logger = logging.getLogger(__name__)


class VectorService:
    """向量检索服务（Milvus）"""

    def __init__(self):
        self.collection: Collection | None = None
        self._connect()

    def _connect(self):
        """连接到 Milvus"""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
            )
            self.collection = Collection(settings.MILVUS_COLLECTION)
            self.collection.load()
            logger.info(f"Connected to Milvus: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            # 不抛出异常，允许服务启动（降级模式）

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        tenant_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalDocument]:
        """
        向量检索

        Args:
            query_embedding: 查询向量
            top_k: 返回的文档数量
            tenant_id: 租户ID
            filters: 过滤条件

        Returns:
            检索到的文档列表
        """
        if not self.collection:
            logger.warning("Milvus not connected, returning empty results")
            return []

        try:
            start_time = time.time()

            # 构建表达式
            expr = self._build_expression(tenant_id, filters)

            # 执行检索
            search_params = {
                "metric_type": "IP",  # Inner Product (Cosine Similarity)
                "params": {"ef": 128},
            }

            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["chunk_id", "document_id", "content", "metadata"],
            )

            # 转换结果
            documents = []
            for hits in results:
                for hit in hits:
                    doc = RetrievalDocument(
                        id=hit.entity.get("document_id", ""),
                        chunk_id=hit.entity.get("chunk_id", ""),
                        content=hit.entity.get("content", ""),
                        score=float(hit.score),
                        metadata=hit.entity.get("metadata", {}),
                        source="vector",
                    )
                    documents.append(doc)

            latency = (time.time() - start_time) * 1000
            logger.info(f"Vector search completed: {len(documents)} documents, latency={latency:.2f}ms")

            return documents

        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            return []

    def _build_expression(
        self, tenant_id: str | None = None, filters: dict[str, Any] | None = None
    ) -> str:
        """构建 Milvus 表达式"""
        expressions = []

        if tenant_id:
            expressions.append(f'tenant_id == "{tenant_id}"')

        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    expressions.append(f'{key} == "{value}"')
                elif isinstance(value, (int, float)):
                    expressions.append(f"{key} == {value}")
                elif isinstance(value, list):
                    # IN 操作
                    if all(isinstance(v, str) for v in value):
                        values_str = ", ".join([f'"{v}"' for v in value])
                        expressions.append(f"{key} in [{values_str}]")
                    else:
                        values_str = ", ".join([str(v) for v in value])
                        expressions.append(f"{key} in [{values_str}]")

        return " && ".join(expressions) if expressions else ""

    def close(self):
        """关闭连接"""
        try:
            connections.disconnect(alias="default")
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Failed to disconnect from Milvus: {e}")
