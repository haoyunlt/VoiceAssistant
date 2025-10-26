"""Milvus 向量数据库后端"""

import logging
import time
from typing import Any, Dict, List, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.core.base_backend import VectorStoreBackend

logger = logging.getLogger(__name__)


class MilvusBackend(VectorStoreBackend):
    """Milvus 向量数据库后端"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.collections: Dict[str, Collection] = {}
        self.alias = "default"

    async def initialize(self):
        """初始化 Milvus 连接"""
        try:
            connections.connect(
                alias=self.alias,
                host=self.config["host"],
                port=self.config["port"],
                user=self.config.get("user", ""),
                password=self.config.get("password", ""),
            )
            self.initialized = True
            logger.info(f"Connected to Milvus at {self.config['host']}:{self.config['port']}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            connections.disconnect(self.alias)
            self.initialized = False
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Error disconnecting from Milvus: {e}")

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 尝试列出集合
            utility.list_collections()
            return True
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")
            return False

    def _get_or_create_collection(self, collection_name: str, dimension: int = 1024) -> Collection:
        """获取或创建集合"""
        # 检查缓存
        if collection_name in self.collections:
            return self.collections[collection_name]

        # 检查是否存在
        if utility.has_collection(collection_name):
            logger.info(f"Collection {collection_name} exists, loading...")
            collection = Collection(collection_name)
            collection.load()
        else:
            logger.info(f"Creating collection: {collection_name}")
            collection = self._create_collection(collection_name, dimension)

        # 缓存
        self.collections[collection_name] = collection
        return collection

    def _create_collection(self, collection_name: str, dimension: int) -> Collection:
        """创建集合"""
        # 定义 Schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]

        schema = CollectionSchema(fields=fields, description=f"{collection_name} collection")

        # 创建集合
        collection = Collection(name=collection_name, schema=schema)

        # 创建索引 (HNSW)
        index_params = {
            "metric_type": "IP",  # Inner Product (Cosine Similarity)
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256},
        }

        collection.create_index(field_name="embedding", index_params=index_params)

        # 加载到内存
        collection.load()

        logger.info(f"Collection {collection_name} created successfully")

        return collection

    async def insert_vectors(
        self,
        collection_name: str,
        data: List[Dict],
    ) -> Any:
        """插入向量"""
        if not data:
            logger.warning("Empty data list for insertion")
            return None

        # 获取或创建集合
        dimension = len(data[0]["embedding"])
        collection = self._get_or_create_collection(collection_name, dimension)

        # 准备数据
        entities = [
            [item["chunk_id"] for item in data],
            [item["document_id"] for item in data],
            [item["content"] for item in data],
            [item["embedding"] for item in data],
            [item.get("tenant_id", "default") for item in data],
            [int(time.time() * 1000) for _ in data],
        ]

        # 插入
        result = collection.insert(entities)

        # 刷新
        collection.flush()

        logger.info(f"Inserted {len(data)} vectors into Milvus collection {collection_name}")

        return result

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
        # 获取集合
        dimension = len(query_vector)
        collection = self._get_or_create_collection(collection_name, dimension)

        # 构建过滤表达式
        expr = []
        if tenant_id:
            expr.append(f'tenant_id == "{tenant_id}"')
        if filters:
            expr.append(filters)

        expr_str = " && ".join(expr) if expr else None

        # 搜索参数
        if search_params is None:
            search_params = {"metric_type": "IP", "params": {"ef": 128}}

        # 执行搜索
        results = collection.search(
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
                    "backend": "milvus",
                })

        logger.info(f"Milvus search returned {len(output)} results")

        return output

    async def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> Any:
        """删除文档的所有向量"""
        collection = self._get_or_create_collection(collection_name)

        expr = f'document_id == "{document_id}"'
        result = collection.delete(expr)

        logger.info(f"Deleted vectors for document {document_id} from Milvus")

        return result

    async def get_count(self, collection_name: str) -> int:
        """获取集合中的向量数量"""
        if not utility.has_collection(collection_name):
            return 0

        collection = self._get_or_create_collection(collection_name)
        return collection.num_entities

    async def create_collection(
        self,
        collection_name: str,
        dimension: int,
        **kwargs,
    ):
        """创建集合"""
        if utility.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} already exists")
            return

        self._create_collection(collection_name, dimension)

    async def drop_collection(self, collection_name: str):
        """删除集合"""
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            if collection_name in self.collections:
                del self.collections[collection_name]
            logger.info(f"Dropped collection {collection_name}")
        else:
            logger.warning(f"Collection {collection_name} does not exist")
