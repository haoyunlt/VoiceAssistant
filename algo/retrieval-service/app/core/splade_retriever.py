"""
SPLADE Retriever - 底层检索器实现

负责与Elasticsearch交互，执行learned sparse检索
"""

import asyncio

import httpx

from app.observability.logging import logger


class SPLADERetriever:
    """SPLADE检索器"""

    def __init__(
        self,
        elasticsearch_endpoint: str = "http://localhost:9200",
        index_name: str = "splade_documents",
        timeout: float = 5.0,
    ):
        """
        初始化SPLADE检索器

        Args:
            elasticsearch_endpoint: ES端点
            index_name: 索引名称
            timeout: 超时时间
        """
        self.elasticsearch_endpoint = elasticsearch_endpoint
        self.index_name = index_name
        self.timeout = timeout

        logger.info(
            f"SPLADE retriever initialized: endpoint={elasticsearch_endpoint}, index={index_name}"
        )

    async def search(
        self,
        query_sparse: dict[str, float],
        top_k: int = 10,
        tenant_id: str | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """
        执行SPLADE检索

        Args:
            query_sparse: Query稀疏向量
            top_k: 返回数量
            tenant_id: 租户ID
            filters: 过滤条件

        Returns:
            检索结果列表
        """
        try:
            # 构建ES查询
            es_query = self._build_sparse_query(query_sparse, tenant_id, filters)

            # 调用ES
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.elasticsearch_endpoint}/{self.index_name}/_search",
                    json={
                        "query": es_query,
                        "size": top_k,
                    },
                )
                response.raise_for_status()
                result = response.json()

            # 解析结果
            documents = []
            for hit in result.get("hits", {}).get("hits", []):
                doc = {
                    "id": hit["_id"],
                    "content": hit["_source"].get("content", ""),
                    "score": hit["_score"],
                    "metadata": hit["_source"].get("metadata", {}),
                }
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error(f"SPLADE retriever HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"SPLADE retriever error: {e}", exc_info=True)
            return []

    def _build_sparse_query(
        self,
        query_sparse: dict[str, float],
        tenant_id: str | None,
        filters: dict | None,
    ) -> dict:
        """
        构建ES稀疏向量查询

        Args:
            query_sparse: 查询稀疏向量
            tenant_id: 租户ID
            filters: 过滤条件

        Returns:
            ES查询DSL
        """
        # ES 7.x+ sparse_vector查询
        must_clauses = [
            {
                "text_expansion": {
                    "splade_vector": {
                        "model_id": ".elser_model_1",
                        "model_text": query_sparse,
                    }
                }
            }
        ]

        # 添加过滤条件
        filter_clauses = []
        if tenant_id:
            filter_clauses.append({"term": {"tenant_id": tenant_id}})

        if filters:
            for key, value in filters.items():
                filter_clauses.append({"term": {key: value}})

        query = {
            "bool": {
                "must": must_clauses,
                "filter": filter_clauses,
            }
        }

        return query

    async def index_documents(
        self,
        documents: list[dict],
        batch_size: int = 100,
    ) -> bool:
        """
        索引文档到SPLADE index

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

                # 构建bulk请求
                bulk_body = []
                for doc in batch:
                    bulk_body.append({"index": {"_index": self.index_name}})
                    bulk_body.append(doc)

                # 执行bulk
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{self.elasticsearch_endpoint}/_bulk",
                        json=bulk_body,
                    )
                    response.raise_for_status()

                logger.info(f"Indexed batch {i // batch_size + 1}")

            logger.info(f"SPLADE indexing completed: {len(documents)} documents")
            return True

        except Exception as e:
            logger.error(f"SPLADE indexing failed: {e}", exc_info=True)
            return False


# 使用示例
if __name__ == "__main__":

    async def test():
        retriever = SPLADERetriever()

        # 模拟query sparse vector
        query_sparse = {
            "python": 1.2,
            "programming": 0.8,
            "tutorial": 0.9,
            "guide": 0.6,
        }

        # 搜索
        results = await retriever.search(query_sparse, top_k=10)
        print(f"Retrieved {len(results)} documents")

    asyncio.run(test())
