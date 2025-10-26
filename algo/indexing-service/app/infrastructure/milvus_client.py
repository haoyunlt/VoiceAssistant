"""
Milvus 客户端 - 向量数据库
"""

import logging
from typing import Dict, List

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

logger = logging.getLogger(__name__)


class MilvusClient:
    """Milvus 向量数据库客户端"""

    def __init__(
        self,
        host: str = "milvus",
        port: int = 19530,
        collection_name: str = "document_chunks",
        dimension: int = 1024,
    ):
        """
        初始化 Milvus 客户端

        Args:
            host: Milvus 主机
            port: Milvus 端口
            collection_name: 集合名称
            dimension: 向量维度
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dimension = dimension

        # 连接 Milvus
        self._connect()

        # 创建或加载集合
        self.collection = self._get_or_create_collection()

        logger.info(f"Milvus client initialized: {host}:{port}, collection={collection_name}")

    def _connect(self):
        """连接 Milvus"""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port,
        )
        logger.info("Connected to Milvus")

    def _get_or_create_collection(self) -> Collection:
        """获取或创建集合"""
        if utility.has_collection(self.collection_name):
            logger.info(f"Collection {self.collection_name} already exists, loading...")
            collection = Collection(self.collection_name)
            collection.load()
            return collection

        logger.info(f"Creating collection: {self.collection_name}")

        # 定义 Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description="Document chunks collection")

        # 创建集合
        collection = Collection(name=self.collection_name, schema=schema)

        # 创建索引 (HNSW)
        index_params = {
            "metric_type": "IP",  # Inner Product (Cosine Similarity)
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256},
        }

        collection.create_index(field_name="embedding", index_params=index_params)

        # 加载到内存
        collection.load()

        logger.info(f"Collection {self.collection_name} created successfully")

        return collection

    async def insert(self, data: Dict):
        """
        插入单条数据

        Args:
            data: 数据字典 {chunk_id, document_id, content, embedding, tenant_id}
        """
        await self.insert_batch([data])

    async def insert_batch(self, data_list: List[Dict]):
        """
        批量插入数据

        Args:
            data_list: 数据列表
        """
        if not data_list:
            logger.warning("Empty data list for insertion")
            return

        # 准备数据
        import time

        entities = [
            [item["chunk_id"] for item in data_list],
            [item["document_id"] for item in data_list],
            [item["content"] for item in data_list],
            [item["embedding"] for item in data_list],
            [item.get("tenant_id", "default") for item in data_list],
            [int(time.time() * 1000) for _ in data_list],
        ]

        # 插入
        result = self.collection.insert(entities)

        # 刷新
        self.collection.flush()

        logger.info(f"Inserted {len(data_list)} entities into Milvus")

        return result

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
                })

        logger.info(f"Search returned {len(output)} results")

        return output

    async def delete_by_document(self, document_id: str):
        """
        删除文档的所有分块

        Args:
            document_id: 文档 ID
        """
        expr = f'document_id == "{document_id}"'
        self.collection.delete(expr)

        logger.info(f"Deleted chunks for document: {document_id}")

    async def count(self) -> int:
        """获取集合中的实体数量"""
        return self.collection.num_entities

    async def close(self):
        """关闭连接"""
        connections.disconnect("default")
        logger.info("Milvus connection closed")
