"""BM25 检索器 - 基于倒排索引"""

import logging
from typing import Dict, List

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

        注意：这里简化实现，实际应该：
        1. 从 Milvus 加载所有文档
        2. 或者维护独立的 BM25 索引（如 Elasticsearch）
        """
        # TODO: 实际实现应该从 Milvus 或独立索引加载
        # 这里暂时使用空语料库
        self.corpus = []
        self.corpus_ids = []

        # 构建 BM25 索引（如果有语料）
        if self.corpus:
            tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)

    def _tokenize(self, text: str) -> List[str]:
        """
        分词

        使用 jieba 进行中文分词
        """
        return list(jieba.cut(text))

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        tenant_id: str = None,
        filters: Dict = None,
    ) -> List[Dict]:
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
                results.append({
                    "chunk_id": self.corpus_ids[idx],
                    "content": self.corpus[idx],
                    "score": float(scores[idx]),
                    "method": "bm25",
                })

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
