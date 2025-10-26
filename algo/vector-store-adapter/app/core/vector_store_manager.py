"""向量存储管理器 - 管理多个后端"""

import logging
from typing import Any, Dict, List, Optional

from app.backends.milvus_backend import MilvusBackend
from app.backends.pgvector_backend import PgVectorBackend
from app.core.base_backend import VectorStoreBackend
from app.core.config import config

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """向量存储管理器 - 统一管理多个向量数据库后端"""

    def __init__(self):
        """初始化管理器"""
        self.backends: Dict[str, VectorStoreBackend] = {}
        self.default_backend = config.DEFAULT_BACKEND

    async def initialize(self):
        """初始化所有后端"""
        logger.info("Initializing vector store backends...")

        # 初始化 Milvus
        try:
            milvus_config = config.get_backend_config("milvus")
            milvus_backend = MilvusBackend(milvus_config)
            await milvus_backend.initialize()
            self.backends["milvus"] = milvus_backend
            logger.info("Milvus backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Milvus backend: {e}")

        # 初始化 pgvector
        try:
            pgvector_config = config.get_backend_config("pgvector")
            pgvector_backend = PgVectorBackend(pgvector_config)
            await pgvector_backend.initialize()
            self.backends["pgvector"] = pgvector_backend
            logger.info("pgvector backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pgvector backend: {e}")

        logger.info(f"Vector store manager initialized with {len(self.backends)} backend(s)")

    async def cleanup(self):
        """清理所有后端"""
        logger.info("Cleaning up vector store backends...")

        for backend_name, backend in self.backends.items():
            try:
                await backend.cleanup()
                logger.info(f"{backend_name} backend cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up {backend_name} backend: {e}")

        self.backends.clear()

    async def health_check(self) -> Dict[str, bool]:
        """健康检查所有后端"""
        checks = {}

        for backend_name, backend in self.backends.items():
            try:
                checks[backend_name] = await backend.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {backend_name}: {e}")
                checks[backend_name] = False

        return checks

    def _get_backend(self, backend: str) -> VectorStoreBackend:
        """获取后端实例"""
        if backend not in self.backends:
            raise ValueError(f"Backend {backend} not available. Available: {list(self.backends.keys())}")

        return self.backends[backend]

    async def insert_vectors(
        self,
        collection_name: str,
        backend: str,
        data: List[Dict],
    ) -> Any:
        """
        插入向量

        Args:
            collection_name: 集合名称
            backend: 后端类型
            data: 向量数据列表

        Returns:
            插入结果
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.insert_vectors(collection_name, data)

    async def search_vectors(
        self,
        collection_name: str,
        backend: str,
        query_vector: List[float],
        top_k: int = 10,
        tenant_id: Optional[str] = None,
        filters: Optional[str] = None,
        search_params: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        向量检索

        Args:
            collection_name: 集合名称
            backend: 后端类型
            query_vector: 查询向量
            top_k: 返回结果数
            tenant_id: 租户ID
            filters: 过滤条件
            search_params: 搜索参数

        Returns:
            检索结果列表
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.search_vectors(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
            tenant_id=tenant_id,
            filters=filters,
            search_params=search_params,
        )

    async def delete_by_document(
        self,
        collection_name: str,
        backend: str,
        document_id: str,
    ) -> Any:
        """
        删除文档的所有向量

        Args:
            collection_name: 集合名称
            backend: 后端类型
            document_id: 文档ID

        Returns:
            删除结果
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.delete_by_document(collection_name, document_id)

    async def get_count(
        self,
        collection_name: str,
        backend: str,
    ) -> int:
        """
        获取集合中的向量数量

        Args:
            collection_name: 集合名称
            backend: 后端类型

        Returns:
            向量数量
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.get_count(collection_name)

    async def create_collection(
        self,
        collection_name: str,
        backend: str,
        dimension: int,
        **kwargs,
    ):
        """
        创建集合

        Args:
            collection_name: 集合名称
            backend: 后端类型
            dimension: 向量维度
            **kwargs: 其他参数
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.create_collection(collection_name, dimension, **kwargs)

    async def drop_collection(
        self,
        collection_name: str,
        backend: str,
    ):
        """
        删除集合

        Args:
            collection_name: 集合名称
            backend: 后端类型
        """
        backend_instance = self._get_backend(backend)
        return await backend_instance.drop_collection(collection_name)

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "backends": {},
            "default_backend": self.default_backend,
        }

        for backend_name, backend in self.backends.items():
            stats["backends"][backend_name] = {
                "initialized": backend.initialized,
                "healthy": await backend.health_check(),
            }

        return stats
