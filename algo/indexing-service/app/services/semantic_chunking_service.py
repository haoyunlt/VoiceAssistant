"""
Semantic-based Text Chunking Service
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class SemanticChunkingService:
    """基于语义的文本分块服务"""

    def __init__(
        self,
        embedding_service,
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 100,
        max_chunk_size: int = 500
    ):
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    async def chunk_text(self, text: str) -> list[dict[str, Any]]:
        """语义分块"""
        # 1. 按句子分割
        sentences = self._split_sentences(text)

        if not sentences:
            return []

        # 2. 获取句子embeddings
        embeddings = await self._get_sentence_embeddings(sentences)

        # 3. 计算相似度
        similarities = self._compute_similarities(embeddings)

        # 4. 基于相似度分组
        chunks = self._group_by_similarity(sentences, similarities)

        # 5. 生成chunk metadata
        result = []
        for i, chunk_text in enumerate(chunks):
            result.append({
                "chunk_id": f"chunk_{i}",
                "content": chunk_text,
                "char_count": len(chunk_text),
                "sentence_count": chunk_text.count('。') + chunk_text.count('！') + chunk_text.count('？')
            })

        logger.info(f"Created {len(result)} semantic chunks from text")
        return result

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        import re
        # 按中英文标点分割
        sentences = re.split(r'([。！？.!?]+)', text)

        # 组合句子和标点
        combined = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                combined.append(sentences[i] + sentences[i+1])
            elif sentences[i].strip():
                combined.append(sentences[i])

        return [s.strip() for s in combined if s.strip()]

    async def _get_sentence_embeddings(self, sentences: list[str]) -> np.ndarray:
        """获取句子embeddings"""
        # 批量获取embeddings
        embeddings = await self.embedding_service.embed_batch(sentences)
        return np.array(embeddings)

    def _compute_similarities(self, embeddings: np.ndarray) -> list[float]:
        """计算相邻句子相似度"""
        similarities = []

        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i+1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1])
            )
            similarities.append(sim)

        return similarities

    def _group_by_similarity(
        self,
        sentences: list[str],
        similarities: list[float]
    ) -> list[str]:
        """基于相似度分组"""
        chunks = []
        current_chunk = []
        current_length = 0

        for i, sentence in enumerate(sentences):
            current_chunk.append(sentence)
            current_length += len(sentence)

            # 判断是否应该分块
            should_split = False

            # 条件1: 长度超过最大值
            if current_length >= self.max_chunk_size:
                should_split = True

            # 条件2: 相似度低于阈值且长度足够
            if i < len(similarities):
                if similarities[i] < self.similarity_threshold and current_length >= self.min_chunk_size:
                    should_split = True

            # 条件3: 是最后一个句子
            if i == len(sentences) - 1:
                should_split = True

            if should_split:
                if current_chunk:
                    chunks.append(''.join(current_chunk))
                current_chunk = []
                current_length = 0

        return chunks
