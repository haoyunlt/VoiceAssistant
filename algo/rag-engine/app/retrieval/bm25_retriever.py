"""
BM25 Retriever - BM25 检索器

基于 BM25 算法的关键词检索
"""

from typing import Any

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    BM25Okapi = None

import logging

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25 检索器"""

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ):
        """
        初始化 BM25 检索器

        Args:
            k1: BM25 参数 k1（词频饱和度）
            b: BM25 参数 b（文档长度归一化）
            epsilon: BM25 参数 epsilon（IDF 下界）
        """
        if not BM25_AVAILABLE:
            logger.warning(
                "rank-bm25 not installed. BM25 retrieval disabled. "
                "Install with: pip install rank-bm25"
            )
            self.bm25 = None
        else:
            self.bm25 = None  # 稍后初始化
            self.k1 = k1
            self.b = b
            self.epsilon = epsilon

        self.documents = []
        self.tokenized_corpus = []

        logger.info("BM25 retriever initialized")

    def index_documents(self, documents: list[dict[str, Any]]):
        """
        索引文档

        Args:
            documents: 文档列表，每个文档包含 'text' 或 'content'
        """
        if not BM25_AVAILABLE:
            logger.warning("BM25 not available, skipping indexing")
            return

        try:
            self.documents = documents

            # 提取文本并分词
            self.tokenized_corpus = []
            for doc in documents:
                text = doc.get("text", "") or doc.get("content", "")
                tokens = self._tokenize(text)
                self.tokenized_corpus.append(tokens)

            # 初始化 BM25
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
                logger.info(f"BM25 indexed {len(documents)} documents")
            else:
                logger.warning("No documents to index")

        except Exception as e:
            logger.error(f"BM25 indexing failed: {e}", exc_info=True)

    def retrieve(
        self, query: str, top_k: int = 10, min_score: float = 0.0
    ) -> list[dict[str, Any]]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回的 top-k 结果
            min_score: 最小分数阈值

        Returns:
            检索到的文档列表（包含分数）
        """
        if not self.bm25 or not self.documents:
            logger.warning("BM25 not initialized or no documents indexed")
            return []

        try:
            # 分词查询
            query_tokens = self._tokenize(query)

            # 计算 BM25 分数
            scores = self.bm25.get_scores(query_tokens)

            # 创建结果列表
            results = []
            for i, score in enumerate(scores):
                if score >= min_score:
                    doc = self.documents[i].copy()
                    doc["bm25_score"] = float(score)
                    results.append(doc)

            # 按分数排序
            results = sorted(results, key=lambda x: x["bm25_score"], reverse=True)

            # 返回 top-k
            return results[:top_k]

        except Exception as e:
            logger.error(f"BM25 retrieval failed: {e}", exc_info=True)
            return []

    def _tokenize(self, text: str) -> list[str]:
        """
        分词

        简单的分词实现（中英文混合）

        Args:
            text: 输入文本

        Returns:
            Token 列表
        """
        import re

        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text.lower())

        # 分割成词
        tokens = text.split()

        # 对于中文，按字符分割
        chinese_tokens = []
        for token in tokens:
            if any('\u4e00' <= c <= '\u9fff' for c in token):
                # 包含中文字符，按字符分割
                chinese_tokens.extend(list(token))
            else:
                chinese_tokens.append(token)

        return chinese_tokens

    def health_check(self) -> dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not BM25_AVAILABLE:
            return {
                "healthy": False,
                "error": "rank-bm25 not installed",
            }

        if not self.bm25:
            return {
                "healthy": False,
                "error": "BM25 not initialized (no documents indexed)",
            }

        return {
            "healthy": True,
            "indexed_documents": len(self.documents),
        }


# 全局实例
_bm25_retriever: BM25Retriever | None = None


def get_bm25_retriever() -> BM25Retriever:
    """
    获取 BM25 检索器实例（单例）

    Returns:
        BM25Retriever 实例
    """
    global _bm25_retriever

    if _bm25_retriever is None:
        _bm25_retriever = BM25Retriever()

    return _bm25_retriever
