"""
文档分块器

使用 LangChain 的 RecursiveCharacterTextSplitter
"""

import hashlib
import logging
from typing import Dict, List

from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentChunker:
    """文档分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化分块器

        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 创建 LangChain 分块器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " ", ""],
            length_function=len,
        )

        logger.info(f"Document chunker initialized: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")

    async def chunk(self, text: str, document_id: str) -> List[Dict]:
        """
        分块文档

        Args:
            text: 文档文本
            document_id: 文档 ID

        Returns:
            分块列表，每个分块包含 id、content、metadata
        """
        if not text or not text.strip():
            logger.warning(f"Empty text for document {document_id}")
            return []

        # 使用 LangChain 分块
        chunks = self.splitter.split_text(text)

        # 构建结果
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = self._generate_chunk_id(document_id, i, chunk_text)

            result.append({
                "id": chunk_id,
                "content": chunk_text,
                "index": i,
                "tokens": self._estimate_tokens(chunk_text),
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            })

        logger.info(f"Created {len(result)} chunks for document {document_id}")

        return result

    def _generate_chunk_id(self, document_id: str, index: int, text: str) -> str:
        """
        生成分块 ID

        使用 document_id + index + text_hash 保证唯一性
        """
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"{document_id}_{index}_{text_hash}"

    def _estimate_tokens(self, text: str) -> int:
        """
        估算 Token 数量

        简单估算：中文按字符数，英文按单词数
        更准确的方法是使用 tiktoken
        """
        # 统计中文字符
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")

        # 统计英文单词（简单按空格分割）
        english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])

        # 估算：1 中文字符 ≈ 1.5 tokens, 1 英文单词 ≈ 1.3 tokens
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 1.3)

        return estimated_tokens


class AdaptiveChunker(DocumentChunker):
    """自适应分块器（根据文档类型调整策略）"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        super().__init__(chunk_size, chunk_overlap)

        # 不同文档类型的分块策略
        self.strategies = {
            "code": {
                "separators": ["\n\nclass ", "\n\ndef ", "\n\n", "\n", " "],
                "chunk_size": 800,
                "chunk_overlap": 100,
            },
            "markdown": {
                "separators": ["\n## ", "\n### ", "\n\n", "\n", " "],
                "chunk_size": 600,
                "chunk_overlap": 60,
            },
            "technical": {
                "separators": ["\n\n", "\n", "。", ". ", " "],
                "chunk_size": 700,
                "chunk_overlap": 70,
            },
        }

    async def chunk(self, text: str, document_id: str, doc_type: str = "general") -> List[Dict]:
        """
        自适应分块

        Args:
            text: 文档文本
            document_id: 文档 ID
            doc_type: 文档类型 (code/markdown/technical/general)

        Returns:
            分块列表
        """
        # 根据文档类型调整策略
        if doc_type in self.strategies:
            strategy = self.strategies[doc_type]
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=strategy["chunk_size"],
                chunk_overlap=strategy["chunk_overlap"],
                separators=strategy["separators"],
            )

        # 调用基类方法
        return await super().chunk(text, document_id)
