"""
Vector Store Client - 向量库适配服务客户端
通过vector-store-adapter统一访问向量数据库
"""

import logging
import os
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class VectorStoreClient:
    """向量库适配服务客户端"""

    def __init__(
        self,
        base_url: str = None,
        collection_name: str = None,
        backend: str = None,
        timeout: float = 30.0,
    ):
        """
        初始化客户端

        Args:
            base_url: 向量库适配服务地址（默认从环境变量读取）
            collection_name: 集合名称（默认从环境变量读取）
            backend: 后端类型 (milvus/pgvector)（默认从环境变量读取）
            timeout: 超时时间（秒）
        """
        self.base_url = (
            base_url or os.getenv("VECTOR_STORE_ADAPTER_URL", "http://vector-store-adapter:8003")
        ).rstrip("/")
        self.collection_name = collection_name or os.getenv("VECTOR_COLLECTION_NAME", "document_chunks")
        self.backend = backend or os.getenv("VECTOR_BACKEND", "milvus")
        self.timeout = timeout

        # 创建 HTTP 客户端
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
        )

        logger.info(
            f"VectorStoreClient initialized: {self.base_url}, "
            f"collection={self.collection_name}, backend={self.backend}"
        )

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
        try:
            response = await self.client.post(
                f"/collections/{self.collection_name}/search",
                json={
                    "backend": self.backend,
                    "query_vector": query_vector,
                    "top_k": top_k,
                    "tenant_id": tenant_id,
                    "filters": filters,
                },
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Search returned {result['count']} results via adapter service")

            return result["results"]

        except httpx.HTTPError as e:
            logger.error(f"Error searching vectors: {e}")
            raise

    async def count(self) -> int:
        """获取集合中的实体数量"""
        try:
            response = await self.client.get(
                f"/collections/{self.collection_name}/count",
                params={"backend": self.backend},
            )

            response.raise_for_status()
            result = response.json()

            return result["count"]

        except httpx.HTTPError as e:
            logger.error(f"Error getting count: {e}")
            return 0

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get("/ready")
            response.raise_for_status()
            result = response.json()
            return result.get("ready", False)
        except Exception:
            return False

    async def close(self):
        """关闭连接"""
        await self.client.aclose()
        logger.info("VectorStoreClient connection closed")
