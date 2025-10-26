"""
BM25 search service using Elasticsearch
"""

import time
from typing import Any, Dict, List, Optional

from elasticsearch import AsyncElasticsearch

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.retrieval import RetrievalDocument

logger = get_logger(__name__)


class BM25Service:
    """BM25 检索服务（Elasticsearch）"""

    def __init__(self):
        self.client: Optional[AsyncElasticsearch] = None
        self._connect()

    def _connect(self):
        """连接到 Elasticsearch"""
        try:
            es_config = {
                "hosts": [f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"],
            }
            if settings.ELASTICSEARCH_USER and settings.ELASTICSEARCH_PASSWORD:
                es_config["basic_auth"] = (settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)

            self.client = AsyncElasticsearch(**es_config)
            logger.info(
                f"Connected to Elasticsearch: {settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            # 不抛出异常，允许服务启动（降级模式）

    async def search(
        self,
        query: str,
        top_k: int,
        tenant_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalDocument]:
        """
        BM25 检索

        Args:
            query: 查询文本
            top_k: 返回的文档数量
            tenant_id: 租户ID
            filters: 过滤条件

        Returns:
            检索到的文档列表
        """
        if not self.client:
            logger.warning("Elasticsearch not connected, returning empty results")
            return []

        try:
            start_time = time.time()

            # 构建查询
            es_query = self._build_query(query, tenant_id, filters)

            # 执行检索
            response = await self.client.search(
                index=settings.ELASTICSEARCH_INDEX, body=es_query, size=top_k
            )

            # 转换结果
            documents = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                doc = RetrievalDocument(
                    id=source.get("document_id", ""),
                    chunk_id=source.get("chunk_id", hit["_id"]),
                    content=source.get("content", ""),
                    score=float(hit["_score"]),
                    metadata=source.get("metadata", {}),
                    source="bm25",
                )
                documents.append(doc)

            latency = (time.time() - start_time) * 1000
            logger.info(f"BM25 search completed: {len(documents)} documents, latency={latency:.2f}ms")

            return documents

        except Exception as e:
            logger.error(f"BM25 search failed: {e}", exc_info=True)
            return []

    def _build_query(
        self, query: str, tenant_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """构建 Elasticsearch 查询"""
        # 基础 BM25 查询
        must_clauses = [{"match": {"content": {"query": query, "boost": 1.0}}}]

        # 添加租户过滤
        filter_clauses = []
        if tenant_id:
            filter_clauses.append({"term": {"tenant_id": tenant_id}})

        # 添加自定义过滤
        if filters:
            for key, value in filters.items():
                if isinstance(value, list):
                    filter_clauses.append({"terms": {key: value}})
                else:
                    filter_clauses.append({"term": {key: value}})

        query_body = {"query": {"bool": {"must": must_clauses}}}

        if filter_clauses:
            query_body["query"]["bool"]["filter"] = filter_clauses

        return query_body

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Elasticsearch")
