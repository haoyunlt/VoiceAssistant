"""向量检索器 - 基于 Milvus"""

import logging
from typing import Dict, List

from app.core.embedder import BGE_M3_Embedder
from app.infrastructure.vector_store_client import VectorStoreClient

logger = logging.getLogger(__name__)


class VectorRetriever:
    """向量检索器"""

    def __init__(self):
        """初始化向量检索器"""
        self.vector_store_client = None
        self.embedder = None
        logger.info("Vector retriever created")

    async def initialize(self):
        """初始化组件"""
        # 初始化 Milvus 客户端
        self.vector_store_client = VectorStoreClient()

        # 初始化 Embedder
        self.embedder = BGE_M3_Embedder()

        logger.info("Vector retriever initialized")

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: str = None,
        filters: Dict = None,
    ) -> List[Dict]:
        """
        向量检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            tenant_id: 租户 ID
            filters: 过滤条件

        Returns:
            检索结果列表
        """
        # 向量化查询
        query_embedding = await self.embedder.embed_query(query)

        # 执行检索
        results = await self.vector_store_client.search(
            query_vector=query_embedding,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
        )

        logger.info(f"Vector retrieval: found {len(results)} results")

        return results

    async def count(self) -> int:
        """获取文档数量"""
        if self.vector_store_client:
            return await self.vector_store_client.count()
        return 0

    async def cleanup(self):
        """清理资源"""
        if self.vector_store_client:
            await self.vector_store_client.close()
        logger.info("Vector retriever cleaned up")
