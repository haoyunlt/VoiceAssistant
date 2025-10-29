"""
Contextual Compression Service - 上下文压缩服务

功能:
- 压缩检索到的文档，保留与查询相关的信息
- 减少Token使用，降低成本
- 提高LLM响应速度

压缩策略:
1. 基于查询关键词的句子筛选
2. 语义相似度过滤
3. LLM based压缩（可选，高成本）

目标:
- Token节省40-60%
- 信息保留率≥90%
- 压缩延迟<200ms/doc
"""

import asyncio
import re
import time
from dataclasses import dataclass

from app.models.retrieval import RetrievalDocument


@dataclass
class CompressionResult:
    """压缩结果"""

    original_doc: RetrievalDocument
    compressed_content: str
    original_length: int
    compressed_length: int
    compression_ratio: float  # 压缩率
    retained_sentences: int
    method: str  # keyword, semantic, llm
    latency_ms: float = 0.0


class CompressionService:
    """上下文压缩服务"""

    def __init__(
        self,
        method: str = "keyword",
        min_relevance_score: float = 0.3,
        max_sentences: int | None = None,
    ):
        """
        初始化压缩服务

        Args:
            method: 压缩方法 (keyword, semantic, llm)
            min_relevance_score: 最小相关性分数
            max_sentences: 最多保留句子数
        """
        self.method = method
        self.min_relevance_score = min_relevance_score
        self.max_sentences = max_sentences

    async def compress(self, query: str, document: RetrievalDocument) -> CompressionResult:
        """
        压缩单个文档

        Args:
            query: 用户查询
            document: 原始文档

        Returns:
            压缩结果
        """
        start_time = time.time()

        original_content = document.content
        original_length = len(original_content)

        if self.method == "keyword":
            compressed, retained_count = self._compress_by_keywords(query, original_content)
        elif self.method == "semantic":
            compressed, retained_count = self._compress_by_semantic(query, original_content)
        else:
            compressed, retained_count = original_content, 0

        compressed_length = len(compressed)
        compression_ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0

        latency_ms = (time.time() - start_time) * 1000

        return CompressionResult(
            original_doc=document,
            compressed_content=compressed,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=compression_ratio,
            retained_sentences=retained_count,
            method=self.method,
            latency_ms=latency_ms,
        )

    def _compress_by_keywords(self, query: str, content: str) -> tuple[str, int]:
        """
        基于关键词的压缩

        策略:
        1. 分句
        2. 计算每个句子与查询的关键词重叠度
        3. 保留高相关度的句子

        Args:
            query: 用户查询
            content: 文档内容

        Returns:
            (压缩后内容, 保留句子数)
        """
        # 提取查询关键词
        query_keywords = set(self._extract_keywords(query))

        # 分句
        sentences = self._split_sentences(content)

        if not sentences:
            return content, 0

        # 计算每个句子的相关性分数
        sentence_scores = []
        for sentence in sentences:
            sentence_keywords = set(self._extract_keywords(sentence))
            # 计算Jaccard相似度
            if query_keywords:
                overlap = len(query_keywords & sentence_keywords)
                score = overlap / len(query_keywords)
            else:
                score = 0
            sentence_scores.append((sentence, score))

        # 过滤低相关度句子
        relevant_sentences = [
            sent for sent, score in sentence_scores if score >= self.min_relevance_score
        ]

        # 如果没有匹配的句子，保留分数最高的前N个
        if not relevant_sentences:
            sentence_scores.sort(key=lambda x: x[1], reverse=True)
            relevant_sentences = [s for s, _ in sentence_scores[:3]]

        # 限制最大句子数
        if self.max_sentences and len(relevant_sentences) > self.max_sentences:
            relevant_sentences = relevant_sentences[: self.max_sentences]

        compressed = " ".join(relevant_sentences)
        return compressed, len(relevant_sentences)

    def _compress_by_semantic(self, query: str, content: str) -> tuple[str, int]:
        """
        基于语义的压缩（需要embedding模型）

        Args:
            query: 用户查询
            content: 文档内容

        Returns:
            (压缩后内容, 保留句子数)
        """
        try:
            import sys
            from pathlib import Path
            import numpy as np

            # 添加 common 路径并导入 embedding 服务
            common_path = Path(__file__).parent.parent.parent.parent.parent.parent / "common"
            if str(common_path) not in sys.path:
                sys.path.insert(0, str(common_path))

            # 注意：这里需要同步调用 embedding 服务
            # 实际生产应该通过 HTTP 客户端调用 embedding service
            # 当前简化为使用本地模型（如果可用）

            from sentence_transformers import SentenceTransformer

            # 加载轻量级模型（首次会下载）
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

            # 分句
            sentences = self._split_sentences(content)
            if not sentences:
                return content, 0

            # 计算 embeddings
            query_embedding = model.encode(query)
            sentence_embeddings = model.encode(sentences)

            # 计算余弦相似度
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity(
                [query_embedding],
                sentence_embeddings
            )[0]

            # 过滤低相关度句子
            relevant_sentences = []
            for sentence, similarity in zip(sentences, similarities):
                if similarity >= self.min_relevance_score:
                    relevant_sentences.append(sentence)

            # 如果没有匹配的句子，保留分数最高的前N个
            if not relevant_sentences:
                top_indices = np.argsort(similarities)[::-1][:3]
                relevant_sentences = [sentences[i] for i in top_indices]

            # 限制最大句子数
            if self.max_sentences and len(relevant_sentences) > self.max_sentences:
                relevant_sentences = relevant_sentences[: self.max_sentences]

            compressed = " ".join(relevant_sentences)
            return compressed, len(relevant_sentences)

        except Exception as e:
            # 降级到关键词方法
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Semantic compression failed, fallback to keywords: {e}")
            return self._compress_by_keywords(query, content)

    def _extract_keywords(self, text: str) -> list[str]:
        """
        提取关键词

        Args:
            text: 文本

        Returns:
            关键词列表
        """
        # 简单的关键词提取：分词 + 停用词过滤
        # 实际项目中应该使用jieba等分词工具
        stopwords = {
            "的",
            "了",
            "是",
            "在",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这",
        }

        # 移除标点和空白
        text = re.sub(r"[^\w\s]", " ", text)
        words = text.split()

        # 过滤停用词和短词
        keywords = [w for w in words if w not in stopwords and len(w) > 1]

        return keywords

    def _split_sentences(self, content: str) -> list[str]:
        """
        分句

        Args:
            content: 文档内容

        Returns:
            句子列表
        """
        # 简单的句子分割（中英文）
        sentences = re.split(r"[。！？；.!?;]\s*", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    async def compress_batch(
        self, query: str, documents: list[RetrievalDocument]
    ) -> list[CompressionResult]:
        """
        批量压缩文档

        Args:
            query: 用户查询
            documents: 文档列表

        Returns:
            压缩结果列表
        """
        tasks = [self.compress(query, doc) for doc in documents]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "method": self.method,
            "min_relevance_score": self.min_relevance_score,
            "max_sentences": self.max_sentences,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = CompressionService(method="keyword", min_relevance_score=0.3, max_sentences=5)

        query = "如何使用Python进行数据分析"
        doc = RetrievalDocument(
            doc_id="test1",
            content="Python是一门编程语言。Python在数据分析领域应用广泛。使用pandas和numpy可以进行数据分析。机器学习也常用Python。数据可视化可以用matplotlib。",
            score=0.9,
            metadata={},
        )

        result = await service.compress(query, doc)

        print(f"原始长度: {result.original_length}")
        print(f"压缩后长度: {result.compressed_length}")
        print(f"压缩率: {result.compression_ratio * 100:.1f}%")
        print(f"保留句子数: {result.retained_sentences}")
        print(f"\n原始内容:\n{doc.content}")
        print(f"\n压缩后内容:\n{result.compressed_content}")

    asyncio.run(test())
