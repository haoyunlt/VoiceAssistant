"""
ColBERT Retriever - 底层检索器实现

负责与向量数据库交互，执行late-interaction检索
"""

import asyncio

import httpx
import numpy as np

from app.observability.logging import logger


class ColBERTRetriever:
    """ColBERT检索器"""

    def __init__(
        self,
        vector_store_endpoint: str = "http://vector-store-adapter:8005",
        collection_name: str = "colbert_documents",
        timeout: float = 5.0,
    ):
        """
        初始化ColBERT检索器

        Args:
            vector_store_endpoint: 向量存储服务端点
            collection_name: ColBERT collection名称
            timeout: 超时时间
        """
        self.vector_store_endpoint = vector_store_endpoint
        self.collection_name = collection_name
        self.timeout = timeout

        logger.info(
            f"ColBERT retriever initialized: endpoint={vector_store_endpoint}, "
            f"collection={collection_name}"
        )

    async def search(
        self,
        query_embeddings: np.ndarray,
        top_k: int = 10,
        tenant_id: str | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """
        执行ColBERT检索

        Args:
            query_embeddings: Query token embeddings
            top_k: 返回数量
            tenant_id: 租户ID
            filters: 过滤条件

        Returns:
            检索结果列表
        """
        try:
            # 调用向量存储服务
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.vector_store_endpoint}/api/v1/colbert/search",
                    json={
                        "collection": self.collection_name,
                        "query_embeddings": query_embeddings.tolist(),
                        "top_k": top_k,
                        "tenant_id": tenant_id,
                        "filters": filters or {},
                    },
                )
                response.raise_for_status()
                result = response.json()

            return result.get("documents", [])

        except httpx.HTTPError as e:
            logger.error(f"ColBERT retriever HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"ColBERT retriever error: {e}", exc_info=True)
            return []

    async def index_documents(
        self,
        documents: list[dict],
        batch_size: int = 100,
    ) -> bool:
        """
        索引文档到ColBERT collection

        Args:
            documents: 文档列表
            batch_size: 批处理大小

        Returns:
            是否成功
        """
        try:
            # 批量索引
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.vector_store_endpoint}/api/v1/colbert/index",
                        json={
                            "collection": self.collection_name,
                            "documents": batch,
                        },
                    )
                    response.raise_for_status()

                logger.info(f"Indexed batch {i // batch_size + 1}")

            logger.info(f"ColBERT indexing completed: {len(documents)} documents")
            return True

        except Exception as e:
            logger.error(f"ColBERT indexing failed: {e}", exc_info=True)
            return False


# 使用示例
if __name__ == "__main__":

    async def test():
        retriever = ColBERTRetriever()

        # 模拟query embeddings
        query_embeddings = np.random.randn(5, 128).astype(np.float32)

        # 搜索
        results = await retriever.search(query_embeddings, top_k=10)
        print(f"Retrieved {len(results)} documents")

    asyncio.run(test())
