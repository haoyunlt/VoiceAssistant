"""
语义分块器
基于 Embedding 相似度的语义分块，保持语义完整性
"""

import hashlib
import logging
import re
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SemanticChunker:
    """语义分块器"""

    def __init__(
        self,
        embedder,
        similarity_threshold: float = 0.75,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        overlap_sentences: int = 1,
    ):
        """
        初始化语义分块器

        Args:
            embedder: Embedding 模型
            similarity_threshold: 相似度阈值（低于此值则切分）
            min_chunk_size: 最小块大小（字符数）
            max_chunk_size: 最大块大小（字符数）
            overlap_sentences: 重叠句子数
        """
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences

        logger.info(
            f"SemanticChunker initialized: threshold={similarity_threshold}, "
            f"min_size={min_chunk_size}, max_size={max_chunk_size}"
        )

    async def chunk(
        self,
        text: str,
        document_id: str,
    ) -> list[dict[str, Any]]:
        """
        基于语义相似度的分块

        策略:
        1. 按句子分割文本
        2. 计算相邻句子的 embedding 相似度
        3. 在相似度低于阈值处切分
        4. 保证分块大小在合理范围内

        Args:
            text: 文档文本
            document_id: 文档 ID

        Returns:
            分块列表
        """
        if not text or not text.strip():
            logger.warning(f"Empty text for document {document_id}")
            return []

        # 1. 按句子分割
        sentences = self._split_sentences(text)

        if len(sentences) == 0:
            return []

        if len(sentences) == 1:
            # 只有一句话，直接返回
            return [
                {
                    "id": self._generate_chunk_id(document_id, 0, sentences[0]),
                    "content": sentences[0],
                    "index": 0,
                    "tokens": self._estimate_tokens(sentences[0]),
                    "metadata": {
                        "document_id": document_id,
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "chunking_method": "semantic",
                    },
                }
            ]

        # 2. 计算句子 embeddings
        logger.debug(f"Computing embeddings for {len(sentences)} sentences")
        sentence_embeddings = await self._compute_sentence_embeddings(sentences)

        # 3. 计算相邻句子相似度
        similarities = self._compute_pairwise_similarities(sentence_embeddings)

        # 4. 找到切分点（相似度低的位置）
        split_indices = self._find_split_points(
            sentences=sentences,
            similarities=similarities,
        )

        # 5. 根据切分点生成分块
        chunks = self._create_chunks(
            sentences=sentences,
            split_indices=split_indices,
            document_id=document_id,
        )

        logger.info(
            f"Semantic chunking completed: {len(chunks)} chunks from {len(sentences)} sentences"
        )

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """
        按句子分割文本

        支持中英文句子分割

        Args:
            text: 文本

        Returns:
            句子列表
        """
        # 中文句子结束符
        chinese_pattern = r'[。！？；]+'

        # 英文句子结束符
        english_pattern = r'[.!?;]+\s+'

        # 组合模式
        pattern = f'({chinese_pattern}|{english_pattern})'

        # 分割
        segments = re.split(pattern, text)

        # 重组句子（将分隔符加回去）
        sentences = []
        current_sentence = ""

        for i, segment in enumerate(segments):
            if segment.strip():
                if re.match(pattern, segment):
                    # 分隔符，加到当前句子
                    current_sentence += segment
                    sentences.append(current_sentence.strip())
                    current_sentence = ""
                else:
                    # 文本，追加到当前句子
                    current_sentence += segment

        # 处理最后一个句子
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        return [s for s in sentences if len(s.strip()) > 0]

    async def _compute_sentence_embeddings(
        self,
        sentences: list[str],
    ) -> np.ndarray:
        """
        计算句子 embeddings

        Args:
            sentences: 句子列表

        Returns:
            Embeddings 矩阵 (n_sentences, embedding_dim)
        """
        # 批量计算 embeddings
        embeddings = await self.embedder.embed_batch(sentences)

        return np.array(embeddings)

    def _compute_pairwise_similarities(
        self,
        embeddings: np.ndarray,
    ) -> list[float]:
        """
        计算相邻句子的相似度

        Args:
            embeddings: Embeddings 矩阵

        Returns:
            相似度列表 (长度为 n_sentences - 1)
        """
        similarities = []

        for i in range(len(embeddings) - 1):
            # 计算相邻两个句子的余弦相似度
            sim = cosine_similarity(
                embeddings[i : i + 1],
                embeddings[i + 1 : i + 2],
            )[0][0]
            similarities.append(float(sim))

        return similarities

    def _find_split_points(
        self,
        sentences: list[str],
        similarities: list[float],
    ) -> list[int]:
        """
        找到切分点

        策略:
        1. 相似度低于阈值的位置
        2. 保证分块大小在合理范围内

        Args:
            sentences: 句子列表
            similarities: 相似度列表

        Returns:
            切分点索引列表
        """
        split_indices = [0]  # 起始点
        current_chunk_size = 0

        for i, (sentence, similarity) in enumerate(zip(sentences, similarities + [0.0], strict=False)):
            current_chunk_size += len(sentence)

            # 判断是否需要切分
            should_split = False

            # 条件1: 相似度低于阈值
            if i < len(similarities) and similarity < self.similarity_threshold:
                should_split = True

            # 条件2: 当前块大小超过最大值
            if current_chunk_size >= self.max_chunk_size:
                should_split = True

            # 条件3: 当前块大小足够，且相似度较低
            if (
                current_chunk_size >= self.min_chunk_size
                and i < len(similarities)
                and similarity < self.similarity_threshold + 0.1
            ):
                should_split = True

            if should_split and i > split_indices[-1]:
                split_indices.append(i + 1)
                current_chunk_size = 0

        # 添加结束点
        if split_indices[-1] < len(sentences):
            split_indices.append(len(sentences))

        return split_indices

    def _create_chunks(
        self,
        sentences: list[str],
        split_indices: list[int],
        document_id: str,
    ) -> list[dict[str, Any]]:
        """
        根据切分点创建分块

        Args:
            sentences: 句子列表
            split_indices: 切分点索引列表
            document_id: 文档 ID

        Returns:
            分块列表
        """
        chunks = []

        for i in range(len(split_indices) - 1):
            start_idx = split_indices[i]
            end_idx = split_indices[i + 1]

            # 添加重叠句子（从前一个块）
            if i > 0 and self.overlap_sentences > 0:
                overlap_start = max(split_indices[i - 1], start_idx - self.overlap_sentences)
                chunk_sentences = sentences[overlap_start:end_idx]
            else:
                chunk_sentences = sentences[start_idx:end_idx]

            # 合并句子
            chunk_text = " ".join(chunk_sentences)

            # 生成分块
            chunks.append(
                {
                    "id": self._generate_chunk_id(document_id, i, chunk_text),
                    "content": chunk_text,
                    "index": i,
                    "tokens": self._estimate_tokens(chunk_text),
                    "metadata": {
                        "document_id": document_id,
                        "chunk_index": i,
                        "total_chunks": len(split_indices) - 1,
                        "sentence_count": len(chunk_sentences),
                        "chunking_method": "semantic",
                    },
                }
            )

        return chunks

    def _generate_chunk_id(self, document_id: str, index: int, text: str) -> str:
        """生成分块 ID"""
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"{document_id}_chunk_{index}_{text_hash}"

    def _estimate_tokens(self, text: str) -> int:
        """估算 Token 数量"""
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])
        return int(chinese_chars * 1.5 + english_words * 1.3)


class AdaptiveSemanticChunker(SemanticChunker):
    """自适应语义分块器（动态调整阈值）"""

    async def chunk(
        self,
        text: str,
        document_id: str,
    ) -> list[dict[str, Any]]:
        """
        自适应语义分块

        策略:
        1. 先尝试使用默认阈值
        2. 如果分块数量过多或过少，动态调整阈值
        3. 重新分块

        Args:
            text: 文档文本
            document_id: 文档 ID

        Returns:
            分块列表
        """
        # 第一次尝试
        chunks = await super().chunk(text, document_id)

        # 评估分块质量
        avg_chunk_size = sum(len(c["content"]) for c in chunks) / len(chunks) if chunks else 0

        # 如果平均块太小，降低阈值（更少的分块）
        if avg_chunk_size < self.min_chunk_size * 0.8:
            logger.info(
                f"Chunks too small (avg={avg_chunk_size:.0f}), "
                f"adjusting threshold from {self.similarity_threshold} to "
                f"{self.similarity_threshold - 0.1}"
            )
            self.similarity_threshold -= 0.1
            chunks = await super().chunk(text, document_id)

        # 如果平均块太大，提高阈值（更多的分块）
        elif avg_chunk_size > self.max_chunk_size * 0.8:
            logger.info(
                f"Chunks too large (avg={avg_chunk_size:.0f}), "
                f"adjusting threshold from {self.similarity_threshold} to "
                f"{self.similarity_threshold + 0.1}"
            )
            self.similarity_threshold += 0.1
            chunks = await super().chunk(text, document_id)

        return chunks
