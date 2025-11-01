"""
Elasticsearch Service - 完整实现
BM25 全文检索服务
增强版：连接池、重试机制、资源管理
"""

import logging
import os
from datetime import datetime

from elasticsearch import AsyncElasticsearch, ConnectionError, TransportError

logger = logging.getLogger(__name__)


class ElasticsearchService:
    """Elasticsearch 服务 - 增强版"""

    def __init__(self, max_retries: int = 3, timeout: int = 30, maxsize: int = 25):
        """
        初始化 Elasticsearch 服务

        Args:
            max_retries: 最大重试次数
            timeout: 请求超时（秒）
            maxsize: 每个节点的连接池大小
        """
        es_host = os.getenv("ELASTICSEARCH_HOST", "localhost")
        es_port = int(os.getenv("ELASTICSEARCH_PORT", 9200))

        self.client = AsyncElasticsearch(
            hosts=[{"host": es_host, "port": es_port, "scheme": "http"}],
            verify_certs=False,
            request_timeout=timeout,
            max_retries=max_retries,
            retry_on_timeout=True,
            # 连接池配置
            maxsize=maxsize,
        )

        self.index_prefix = "voiceassistant"
        self._is_closed = False

        logger.info(
            f"Elasticsearch service initialized: host={es_host}:{es_port} "
            f"max_retries={max_retries} timeout={timeout}s pool_size={maxsize}"
        )

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()

    def _check_closed(self):
        """检查服务是否已关闭"""
        if self._is_closed:
            raise RuntimeError("ElasticsearchService is closed")

    async def create_index(self, tenant_id: str, kb_id: str, settings: dict = None):
        """
        创建索引

        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            settings: 自定义设置
        """
        self._check_closed()
        index_name = self._get_index_name(tenant_id, kb_id)

        try:
            # 检查索引是否已存在
            if await self.client.indices.exists(index=index_name):
                logger.info(f"Index {index_name} already exists")
                return
        except (ConnectionError, TransportError) as e:
            logger.error(f"Failed to check index existence: {e}")
            raise

        # 定义映射
        mappings = {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "document_id": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",  # 中文分词
                    "search_analyzer": "ik_smart",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "english": {"type": "text", "analyzer": "english"},
                    },
                },
                "title": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "fields": {"keyword": {"type": "keyword"}},
                },
                "metadata": {"type": "object", "enabled": True},
                "created_at": {"type": "date"},
                "tenant_id": {"type": "keyword"},
                "kb_id": {"type": "keyword"},
            }
        }

        # 定义设置
        if settings is None:
            settings = {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "ik_max_word": {"type": "custom", "tokenizer": "ik_max_word"},
                        "ik_smart": {"type": "custom", "tokenizer": "ik_smart"},
                    }
                },
            }

        # 创建索引
        await self.client.indices.create(
            index=index_name, body={"settings": settings, "mappings": mappings}
        )

        logger.info(f"Created ES index: {index_name}")

    async def index_document(
        self,
        tenant_id: str,
        kb_id: str,
        chunk_id: str,
        document_id: str,
        content: str,
        title: str = "",
        metadata: dict = None,
    ):
        """
        索引文档

        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            chunk_id: 文档块 ID
            document_id: 文档 ID
            content: 内容
            title: 标题
            metadata: 元数据
        """
        index_name = self._get_index_name(tenant_id, kb_id)

        doc = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "content": content,
            "title": title,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "kb_id": kb_id,
        }

        await self.client.index(index=index_name, id=chunk_id, body=doc)

        logger.debug(f"Indexed document chunk: {chunk_id}")

    async def search(
        self,
        tenant_id: str,
        kb_id: str,
        query: str,
        top_k: int = 50,
        filters: dict = None,
        min_score: float = None,
    ) -> list[dict]:
        """
        BM25 搜索 - 带自动重试

        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 返回数量
            filters: 过滤条件
            min_score: 最小分数阈值

        Returns:
            List[Dict]: 检索结果
        """
        self._check_closed()
        index_name = self._get_index_name(tenant_id, kb_id)

        try:
            # 检查索引是否存在
            if not await self.client.indices.exists(index=index_name):
                logger.warning(f"Index {index_name} does not exist")
                return []
        except (ConnectionError, TransportError) as e:
            logger.error(f"Failed to check index existence: {e}")
            return []

        # 构建查询
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "title^1.5"],
                    "type": "best_fields",
                    "operator": "or",
                    "fuzziness": "AUTO",
                }
            }
        ]

        # 添加过滤条件
        filter_clauses = []
        if filters:
            for key, value in filters.items():
                filter_clauses.append({"term": {f"metadata.{key}": value}})

        # 构建查询体
        query_body = {
            "query": {
                "bool": {"must": must_clauses, "filter": filter_clauses if filter_clauses else []}
            },
            "size": top_k,
            "_source": ["chunk_id", "document_id", "content", "title", "metadata"],
            "highlight": {"fields": {"content": {"fragment_size": 150, "number_of_fragments": 3}}},
        }

        # 添加最小分数过滤
        if min_score:
            query_body["min_score"] = min_score

        # 执行搜索（AsyncElasticsearch 内置重试机制）
        try:
            response = await self.client.search(index=index_name, body=query_body)
        except ConnectionError as e:
            logger.error(f"Elasticsearch connection error: {e}", exc_info=True)
            return []
        except TransportError as e:
            logger.error(f"Elasticsearch transport error: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Search failed with unexpected error: {e}", exc_info=True)
            return []

        # 提取结果
        results = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]

            # 提取高亮片段
            highlights = []
            if "highlight" in hit and "content" in hit["highlight"]:
                highlights = hit["highlight"]["content"]

            results.append(
                {
                    "chunk_id": source["chunk_id"],
                    "document_id": source["document_id"],
                    "content": source["content"],
                    "title": source.get("title", ""),
                    "score": hit["_score"],
                    "metadata": source.get("metadata", {}),
                    "highlights": highlights,
                    "source": "bm25",
                }
            )

        logger.info(f"BM25 search returned {len(results)} results")
        return results

    async def bulk_index(self, tenant_id: str, kb_id: str, documents: list[dict]):
        """
        批量索引

        Args:
            tenant_id: 租户 ID
            kb_id: 知识库 ID
            documents: 文档列表，每个文档包含 chunk_id, document_id, content, title, metadata
        """
        index_name = self._get_index_name(tenant_id, kb_id)

        # 构建批量操作
        bulk_body = []
        for doc in documents:
            # 添加索引动作
            bulk_body.append({"index": {"_index": index_name, "_id": doc["chunk_id"]}})

            # 添加文档数据
            bulk_body.append(
                {
                    "chunk_id": doc["chunk_id"],
                    "document_id": doc["document_id"],
                    "content": doc["content"],
                    "title": doc.get("title", ""),
                    "metadata": doc.get("metadata", {}),
                    "created_at": datetime.utcnow().isoformat(),
                    "tenant_id": tenant_id,
                    "kb_id": kb_id,
                }
            )

        # 执行批量操作
        if bulk_body:
            response = await self.client.bulk(body=bulk_body)

            # 检查错误
            if response.get("errors"):
                error_count = sum(
                    1 for item in response["items"] if "error" in item.get("index", {})
                )
                logger.warning(f"Bulk index completed with {error_count} errors")
            else:
                logger.info(f"Bulk indexed {len(documents)} documents")

    async def delete_document(self, tenant_id: str, kb_id: str, chunk_id: str):
        """删除文档"""
        index_name = self._get_index_name(tenant_id, kb_id)

        try:
            await self.client.delete(index=index_name, id=chunk_id)
            logger.debug(f"Deleted document chunk: {chunk_id}")
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")

    async def delete_index(self, tenant_id: str, kb_id: str):
        """删除索引"""
        index_name = self._get_index_name(tenant_id, kb_id)

        try:
            await self.client.indices.delete(index=index_name)
            logger.info(f"Deleted index: {index_name}")
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")

    async def get_index_stats(self, tenant_id: str, kb_id: str) -> dict:
        """获取索引统计信息"""
        index_name = self._get_index_name(tenant_id, kb_id)

        try:
            stats = await self.client.indices.stats(index=index_name)

            index_stats = stats["indices"].get(index_name, {})
            total_stats = index_stats.get("total", {})

            return {
                "document_count": total_stats.get("docs", {}).get("count", 0),
                "storage_size_bytes": total_stats.get("store", {}).get("size_in_bytes", 0),
                "index_name": index_name,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}

    async def close(self):
        """关闭客户端 - 确保资源清理"""
        if not self._is_closed:
            try:
                await self.client.close()
                self._is_closed = True
                logger.info("Elasticsearch client closed successfully")
            except Exception as e:
                logger.error(f"Error closing Elasticsearch client: {e}", exc_info=True)
                # 即使关闭失败也标记为已关闭
                self._is_closed = True

    def _get_index_name(self, tenant_id: str, kb_id: str) -> str:
        """生成索引名称"""
        return f"{self.index_prefix}_{tenant_id}_{kb_id}".lower()
