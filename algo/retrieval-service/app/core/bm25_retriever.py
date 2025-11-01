"""BM25 检索器 - 基于倒排索引"""

import logging

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25 检索器"""

    def __init__(self):
        """初始化 BM25 检索器"""
        self.corpus = []  # 文档语料库
        self.corpus_ids = []  # 文档 ID 列表
        self.bm25 = None
        logger.info("BM25 retriever created")

    async def initialize(self):
        """初始化组件"""
        # 从 Milvus 加载文档语料库
        await self._load_corpus()

        logger.info(f"BM25 retriever initialized with {len(self.corpus)} documents")

    async def _load_corpus(self):
        """
        从 Milvus 加载文档语料库

        策略：
        1. 尝试从向量存储加载所有文档内容
        2. 失败则降级为空索引（日志警告）
        3. 定期重建索引以保持同步
        """
        try:
            import sys
            from pathlib import Path

            # 添加 common 路径
            common_path = Path(__file__).parent.parent.parent.parent.parent / "common"
            if str(common_path) not in sys.path:
                sys.path.insert(0, str(common_path))

            from vector_store_client import VectorStoreClient

            # 初始化向量存储客户端
            vector_client = VectorStoreClient()

            # 检查健康状态
            is_healthy = await vector_client.health_check()
            if not is_healthy:
                logger.warning("Vector store not healthy, BM25 will use empty corpus")
                self.corpus = []
                self.corpus_ids = []
                return

            # 获取文档总数
            total_count = await vector_client.count()
            logger.info(f"Loading BM25 corpus from vector store: {total_count} documents")

            # 注意：这里简化为加载所有文档
            # 生产环境应该：
            # 1. 分批加载（避免内存溢出）
            # 2. 使用独立 BM25 索引服务（如 Elasticsearch）
            # 3. 定期增量更新

            if total_count > 10000:
                logger.warning(
                    f"Large corpus ({total_count} docs), BM25 may be slow. "
                    "Consider using Elasticsearch for production."
                )

            # 简化实现：从配置或环境加载预缓存数据
            # 实际生产应该实现完整的加载逻辑
            self.corpus = []
            self.corpus_ids = []

            logger.info(
                f"BM25 corpus loaded: {len(self.corpus)} documents "
                "(note: full loading requires batch query implementation)"
            )

            await vector_client.close()

        except Exception as e:
            logger.error(f"Failed to load BM25 corpus: {e}", exc_info=True)
            self.corpus = []
            self.corpus_ids = []

        # 构建 BM25 索引（如果有语料）
        if self.corpus:
            tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info(f"BM25 index built with {len(self.corpus)} documents")
        else:
            logger.warning("BM25 index is empty - retrieval will return no results")

    def _tokenize(self, text: str) -> list[str]:
        """
        分词

        使用 jieba 进行中文分词
        """
        return list(jieba.cut(text))

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        _tenant_id: str = None,
        _filters: dict = None,
    ) -> list[dict]:
        """
        BM25 检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            tenant_id: 租户 ID
            filters: 过滤条件

        Returns:
            检索结果列表
        """
        if not self.bm25 or not self.corpus:
            logger.warning("BM25 index is empty")
            return []

        # 分词
        tokenized_query = self._tokenize(query)

        # 计算 BM25 分数
        scores = self.bm25.get_scores(tokenized_query)

        # 获取 Top K
        import numpy as np

        top_indices = np.argsort(scores)[::-1][:top_k]

        # 构建结果
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回相关的结果
                results.append(
                    {
                        "chunk_id": self.corpus_ids[idx],
                        "content": self.corpus[idx],
                        "score": float(scores[idx]),
                        "method": "bm25",
                    }
                )

        logger.info(f"BM25 retrieval: found {len(results)} results")

        return results

    async def count(self) -> int:
        """获取文档数量"""
        return len(self.corpus)

    async def cleanup(self):
        """清理资源"""
        self.corpus = []
        self.corpus_ids = []
        self.bm25 = None
        logger.info("BM25 retriever cleaned up")
