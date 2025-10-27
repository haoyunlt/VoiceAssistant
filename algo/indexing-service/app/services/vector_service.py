"""向量数据库服务 - 使用统一VectorStoreClient"""
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings

# 添加common目录到Python路径
common_path = Path(__file__).parent.parent.parent.parent / "common"
if str(common_path) not in sys.path:
    sys.path.insert(0, str(common_path))

from vector_store_client import VectorStoreClient

logger = logging.getLogger(__name__)


class VectorService:
    """向量数据库服务 - 使用统一VectorStoreClient"""

    def __init__(self):
        # 使用统一的VectorStoreClient
        self.client = VectorStoreClient()

    async def insert_vectors(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        """
        插入向量到向量存储

        Args:
            document_id: 文档ID
            chunks: 文本块列表
            embeddings: 向量列表

        Returns:
            插入的向量数量
        """
        try:
            # 准备数据
            data = []
            for chunk, embedding in zip(chunks, embeddings):
                data.append({
                    "chunk_id": chunk["id"],
                    "document_id": document_id,
                    "content": chunk["content"],
                    "embedding": embedding,
                })

            # 使用统一客户端插入
            await self.client.insert_batch(data)

            logger.info(f"Inserted {len(data)} vectors for document {document_id}")
            return len(data)

        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}", exc_info=True)
            raise

    async def delete_vectors(self, document_id: str):
        """
        删除文档的所有向量

        Args:
            document_id: 文档ID
        """
        try:
            # 使用统一客户端删除
            await self.client.delete_by_document(document_id)

            logger.info(f"Deleted vectors for document: {document_id}")

        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}", exc_info=True)
            raise

    async def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        相似度搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            filters: 过滤条件

        Returns:
            相似文本块列表
        """
        try:
            # 使用统一客户端搜索
            results = await self.client.search(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters,
            )

            logger.info(f"Searched similar vectors, top_k={top_k}, found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to search vectors: {e}", exc_info=True)
            raise
