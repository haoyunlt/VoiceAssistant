"""Milvus 客户端 - 向量数据库（与 Indexing Service 共享）"""

import logging
from typing import Dict, List

from pymilvus import Collection, connections, utility

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus 向量数据库客户端"""

    def __init__(
        self,
        host: str = "milvus",
        port: int = 19530,
        collection_name: str = "document_chunks",
    ):
        """
        初始化 Milvus 客户端

        Args:
            host: Milvus 主机
            port: Milvus 端口
            collection_name: 集合名称
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name

        # 连接 Milvus
        self._connect()

        # 加载集合
        self.collection = self._load_collection()

        logger.info(f"Milvus client initialized: {host}:{port}, collection={collection_name}")

    def _connect(self):
        """连接 Milvus"""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port,
        )
        logger.info("Connected to Milvus")

    def _load_collection(self) -> Collection:
        """加载集合"""
        if not utility.has_collection(self.collection_name):
            raise Exception(f"Collection {self.collection_name} does not exist")

        collection = Collection(self.collection_name)
        collection.load()

        logger.info(f"Collection {self.collection_name} loaded")

        return collection

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        tenant_id: str = None,
        filters: str = None,
    ) -> List[Dict]:
        """
        向量检索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            tenant_id: 租户 ID（用于过滤）
            filters: 额外过滤条件

        Returns:
            检索结果列表
        """
        # 构建过滤表达式
        expr = []
        if tenant_id:
            expr.append(f'tenant_id == "{tenant_id}"')
        if filters:
            expr.append(filters)

        expr_str = " && ".join(expr) if expr else None

        # 搜索参数
        search_params = {"metric_type": "IP", "params": {"ef": 128}}

        # 执行搜索
        results = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=expr_str,
            output_fields=["chunk_id", "document_id", "content", "tenant_id"],
        )

        # 转换结果
        output = []
        for hits in results:
            for hit in hits:
                output.append({
                    "chunk_id": hit.entity.get("chunk_id"),
                    "document_id": hit.entity.get("document_id"),
                    "content": hit.entity.get("content"),
                    "tenant_id": hit.entity.get("tenant_id"),
                    "score": hit.score,
                    "distance": hit.distance,
                    "method": "vector",
                })

        logger.info(f"Search returned {len(output)} results")

        return output

    async def count(self) -> int:
        """获取集合中的实体数量"""
        return self.collection.num_entities

    async def close(self):
        """关闭连接"""
        connections.disconnect("default")
        logger.info("Milvus connection closed")
