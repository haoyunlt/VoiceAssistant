"""向量存储后端基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class VectorStoreBackend(ABC):
    """向量存储后端抽象基类"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化后端

        Args:
            config: 后端配置
        """
        self.config = config
        self.initialized = False

    @abstractmethod
    async def initialize(self):
        """初始化连接"""
        pass

    @abstractmethod
    async def cleanup(self):
        """清理资源"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    async def insert_vectors(
        self,
        collection_name: str,
        data: List[Dict],
    ) -> Any:
        """
        插入向量

        Args:
            collection_name: 集合名称
            data: 向量数据列表
                - chunk_id: 分块ID
                - document_id: 文档ID
                - content: 内容
                - embedding: 向量
                - tenant_id: 租户ID
                - metadata: 元数据（可选）

        Returns:
            插入结果
        """
        pass

    @abstractmethod
    async def search_vectors(
        self,
        collection_name: str,
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
            query_vector: 查询向量
            top_k: 返回结果数
            tenant_id: 租户ID（用于过滤）
            filters: 额外过滤条件
            search_params: 搜索参数

        Returns:
            检索结果列表
        """
        pass

    @abstractmethod
    async def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
    ) -> Any:
        """
        删除文档的所有向量

        Args:
            collection_name: 集合名称
            document_id: 文档ID

        Returns:
            删除结果
        """
        pass

    @abstractmethod
    async def get_count(self, collection_name: str) -> int:
        """
        获取集合中的向量数量

        Args:
            collection_name: 集合名称

        Returns:
            向量数量
        """
        pass

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        dimension: int,
        **kwargs,
    ):
        """
        创建集合

        Args:
            collection_name: 集合名称
            dimension: 向量维度
            **kwargs: 其他参数
        """
        pass

    @abstractmethod
    async def drop_collection(self, collection_name: str):
        """
        删除集合

        Args:
            collection_name: 集合名称
        """
        pass
