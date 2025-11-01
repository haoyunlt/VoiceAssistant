"""
上下文增强器
为分块添加上下文信息，提升检索效果
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContextEnhancer:
    """上下文增强器"""

    def __init__(
        self,
        include_prev_summary: bool = True,
        include_next_summary: bool = True,
        include_metadata: bool = True,
        include_position: bool = True,
        summary_max_length: int = 100,
    ):
        """
        初始化上下文增强器

        Args:
            include_prev_summary: 是否包含前一个chunk的摘要
            include_next_summary: 是否包含后一个chunk的摘要
            include_metadata: 是否包含文档元数据
            include_position: 是否包含位置信息
            summary_max_length: 摘要最大长度
        """
        self.include_prev_summary = include_prev_summary
        self.include_next_summary = include_next_summary
        self.include_metadata = include_metadata
        self.include_position = include_position
        self.summary_max_length = summary_max_length

        logger.info(
            f"ContextEnhancer initialized: "
            f"prev_summary={include_prev_summary}, "
            f"next_summary={include_next_summary}, "
            f"metadata={include_metadata}"
        )

    async def enhance_chunks(
        self,
        chunks: list[dict[str, Any]],
        document_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        为分块列表添加上下文信息

        策略:
        1. 添加前后 chunk 的摘要
        2. 添加文档元数据（标题、作者等）
        3. 添加位置信息（页码、章节）
        4. 生成增强后的内容

        Args:
            chunks: 分块列表
            document_metadata: 文档元数据

        Returns:
            增强后的分块列表
        """
        if not chunks:
            return []

        enhanced_chunks = []

        for i, chunk in enumerate(chunks):
            # 复制原始chunk
            enhanced_chunk = chunk.copy()

            # 1. 添加前后文摘要
            if self.include_prev_summary and i > 0:
                prev_chunk = chunks[i - 1]
                prev_summary = self._generate_summary(prev_chunk["content"])
                enhanced_chunk["prev_context"] = prev_summary

            if self.include_next_summary and i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                next_summary = self._generate_summary(next_chunk["content"])
                enhanced_chunk["next_context"] = next_summary

            # 2. 添加文档元数据
            if self.include_metadata and document_metadata:
                enhanced_chunk["document_metadata"] = {
                    "title": document_metadata.get("title", ""),
                    "author": document_metadata.get("author", ""),
                    "source": document_metadata.get("source", ""),
                    "tags": document_metadata.get("tags", []),
                }

            # 3. 添加位置信息
            if self.include_position:
                enhanced_chunk["position_info"] = {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "relative_position": i / len(chunks) if len(chunks) > 0 else 0,
                    "is_first": i == 0,
                    "is_last": i == len(chunks) - 1,
                }

            # 4. 生成增强后的内容（用于向量化）
            enhanced_chunk["enhanced_content"] = self._build_enhanced_content(
                chunk=chunk,
                prev_summary=enhanced_chunk.get("prev_context"),
                next_summary=enhanced_chunk.get("next_context"),
                document_metadata=document_metadata,
            )

            enhanced_chunks.append(enhanced_chunk)

        logger.info(f"Enhanced {len(enhanced_chunks)} chunks with context")

        return enhanced_chunks

    def _generate_summary(self, text: str) -> str:
        """
        生成文本摘要

        简单实现：取前N个字符
        高级实现：可以使用LLM生成摘要

        Args:
            text: 文本

        Returns:
            摘要
        """
        if len(text) <= self.summary_max_length:
            return text

        # 简单截断（尽量在句子边界）
        summary = text[: self.summary_max_length]

        # 尝试在句号处截断
        last_period_pos = summary.rfind("。")
        if last_period_pos == -1:
            last_period_pos = summary.rfind(".")

        if last_period_pos > self.summary_max_length * 0.7:
            summary = summary[: last_period_pos + 1]
        else:
            summary += "..."

        return summary.strip()

    def _build_enhanced_content(
        self,
        chunk: dict[str, Any],
        prev_summary: str | None,
        next_summary: str | None,
        document_metadata: dict[str, Any] | None,
    ) -> str:
        """
        构建增强后的内容

        将上下文信息与原始内容组合

        Args:
            chunk: 原始分块
            prev_summary: 前文摘要
            next_summary: 后文摘要
            document_metadata: 文档元数据

        Returns:
            增强后的内容
        """
        parts = []

        # 添加文档元数据
        if document_metadata and document_metadata.get("title"):
            parts.append(f"Document: {document_metadata['title']}")

        # 添加前文上下文
        if prev_summary:
            parts.append(f"Previous context: {prev_summary}")

        # 添加主要内容
        parts.append(chunk["content"])

        # 添加后文上下文
        if next_summary:
            parts.append(f"Next context: {next_summary}")

        return "\n\n".join(parts)

    async def enhance_single_chunk(
        self,
        chunk: dict[str, Any],
        prev_chunk: dict[str, Any] | None = None,
        next_chunk: dict[str, Any] | None = None,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        增强单个分块

        Args:
            chunk: 分块
            prev_chunk: 前一个分块
            next_chunk: 后一个分块
            document_metadata: 文档元数据

        Returns:
            增强后的分块
        """
        enhanced_chunk = chunk.copy()

        # 添加前后文
        if prev_chunk:
            enhanced_chunk["prev_context"] = self._generate_summary(prev_chunk["content"])

        if next_chunk:
            enhanced_chunk["next_context"] = self._generate_summary(next_chunk["content"])

        # 添加元数据
        if document_metadata:
            enhanced_chunk["document_metadata"] = document_metadata

        # 生成增强内容
        enhanced_chunk["enhanced_content"] = self._build_enhanced_content(
            chunk=chunk,
            prev_summary=enhanced_chunk.get("prev_context"),
            next_summary=enhanced_chunk.get("next_context"),
            document_metadata=document_metadata,
        )

        return enhanced_chunk


class HierarchicalContextEnhancer(ContextEnhancer):
    """层级上下文增强器（适用于有层级结构的文档）"""

    async def enhance_chunks(
        self,
        chunks: list[dict[str, Any]],
        document_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        增强分块（考虑层级结构）

        Args:
            chunks: 分块列表
            document_metadata: 文档元数据

        Returns:
            增强后的分块列表
        """
        # 先调用基类方法
        enhanced_chunks = await super().enhance_chunks(chunks, document_metadata)

        # 添加层级上下文
        for chunk in enhanced_chunks:
            # 如果chunk有层级信息（如Markdown标题）
            metadata = chunk.get("metadata", {})

            if "header_level" in metadata:
                # 查找父标题
                parent_header = self._find_parent_header(
                    chunk,
                    chunks,
                )

                if parent_header:
                    chunk["hierarchical_context"] = {
                        "parent_header": parent_header,
                        "level": metadata["header_level"],
                    }

        return enhanced_chunks

    def _find_parent_header(
        self,
        chunk: dict[str, Any],
        all_chunks: list[dict[str, Any]],
    ) -> str | None:
        """
        查找父标题

        Args:
            chunk: 当前分块
            all_chunks: 所有分块

        Returns:
            父标题文本
        """
        current_level = chunk.get("metadata", {}).get("header_level")

        if not current_level or current_level == 1:
            return None

        current_index = chunk.get("index", 0)

        # 向前查找更高级别的标题
        for i in range(current_index - 1, -1, -1):
            prev_chunk = all_chunks[i]
            prev_level = prev_chunk.get("metadata", {}).get("header_level")

            if prev_level and prev_level < current_level:
                return prev_chunk.get("metadata", {}).get("header_text")

        return None


class SemanticContextEnhancer(ContextEnhancer):
    """语义上下文增强器（使用Embedding计算相关性）"""

    def __init__(
        self,
        embedder,
        similarity_threshold: float = 0.7,
        max_related_chunks: int = 3,
        **kwargs,
    ):
        """
        初始化语义上下文增强器

        Args:
            embedder: Embedding模型
            similarity_threshold: 相似度阈值
            max_related_chunks: 最大相关chunk数量
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        self.max_related_chunks = max_related_chunks

    async def enhance_chunks(
        self,
        chunks: list[dict[str, Any]],
        document_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        增强分块（添加语义相关的chunks）

        Args:
            chunks: 分块列表
            document_metadata: 文档元数据

        Returns:
            增强后的分块列表
        """
        # 先调用基类方法
        enhanced_chunks = await super().enhance_chunks(chunks, document_metadata)

        # 计算所有chunk的embeddings
        logger.info(f"Computing embeddings for {len(chunks)} chunks")
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await self.embedder.embed_batch(texts)

        # 为每个chunk找到相关chunks
        for i, chunk in enumerate(enhanced_chunks):
            related_chunks = self._find_related_chunks(
                current_embedding=embeddings[i],
                all_embeddings=embeddings,
                all_chunks=chunks,
                current_index=i,
            )

            if related_chunks:
                chunk["related_chunks"] = related_chunks

        return enhanced_chunks

    def _find_related_chunks(
        self,
        current_embedding: list[float],
        all_embeddings: list[list[float]],
        all_chunks: list[dict[str, Any]],
        current_index: int,
    ) -> list[dict[str, Any]]:
        """
        找到相关的chunks

        Args:
            current_embedding: 当前chunk的embedding
            all_embeddings: 所有embeddings
            all_chunks: 所有chunks
            current_index: 当前索引

        Returns:
            相关chunks列表
        """
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        # 计算与其他chunks的相似度
        current_emb = np.array([current_embedding])
        all_embs = np.array(all_embeddings)

        similarities = cosine_similarity(current_emb, all_embs)[0]

        # 找到相似度高的chunks（排除自己和邻近chunks）
        related_indices = []

        for i, sim in enumerate(similarities):
            # 排除自己和邻近chunks
            if i == current_index or abs(i - current_index) <= 1:
                continue

            # 相似度高于阈值
            if sim >= self.similarity_threshold:
                related_indices.append((i, sim))

        # 按相似度排序，取top-k
        related_indices.sort(key=lambda x: x[1], reverse=True)
        related_indices = related_indices[: self.max_related_chunks]

        # 构建相关chunks信息
        related_chunks = []
        for idx, sim in related_indices:
            related_chunks.append(
                {
                    "chunk_index": idx,
                    "similarity": float(sim),
                    "content_summary": self._generate_summary(all_chunks[idx]["content"]),
                }
            )

        return related_chunks
