"""智能分块服务"""

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """文本块"""

    content: str
    start_index: int
    end_index: int
    chunk_type: str  # paragraph, section, sentence, etc.
    metadata: dict


class SmartChunkingService:
    """智能分块服务"""

    def __init__(self):
        """初始化"""
        self.min_chunk_size = 100  # 最小块大小（字符）
        self.max_chunk_size = 1000  # 最大块大小
        self.overlap_size = 50  # 重叠大小

    async def chunk_by_semantic(
        self, text: str, max_chunk_size: int = None, min_chunk_size: int = None
    ) -> list[Chunk]:
        """语义分块（基于段落和句子）

        Args:
            text: 输入文本
            max_chunk_size: 最大块大小
            min_chunk_size: 最小块大小

        Returns:
            文本块列表
        """
        if max_chunk_size is None:
            max_chunk_size = self.max_chunk_size
        if min_chunk_size is None:
            min_chunk_size = self.min_chunk_size

        chunks = []

        # 1. 按段落分割
        paragraphs = self._split_by_paragraphs(text)

        current_chunk = ""
        current_start = 0

        for para in paragraphs:
            # 如果加上这个段落不超过最大长度，合并
            if len(current_chunk) + len(para) <= max_chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 保存当前块
                if current_chunk and len(current_chunk) >= min_chunk_size:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            start_index=current_start,
                            end_index=current_start + len(current_chunk),
                            chunk_type="semantic",
                            metadata={"method": "paragraph"},
                        )
                    )

                # 如果段落本身太长，按句子分割
                if len(para) > max_chunk_size:
                    sentence_chunks = await self._chunk_long_paragraph(
                        para, max_chunk_size, min_chunk_size
                    )
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                    current_start = chunks[-1].end_index if chunks else 0
                else:
                    current_chunk = para
                    current_start = chunks[-1].end_index if chunks else 0

        # 添加最后一块
        if current_chunk and len(current_chunk) >= min_chunk_size:
            chunks.append(
                Chunk(
                    content=current_chunk.strip(),
                    start_index=current_start,
                    end_index=current_start + len(current_chunk),
                    chunk_type="semantic",
                    metadata={"method": "paragraph"},
                )
            )

        return chunks

    def _split_by_paragraphs(self, text: str) -> list[str]:
        """按段落分割

        Args:
            text: 文本

        Returns:
            段落列表
        """
        # 按双换行符或多个换行符分割
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    async def _chunk_long_paragraph(
        self, paragraph: str, max_chunk_size: int, min_chunk_size: int
    ) -> list[Chunk]:
        """分块长段落

        Args:
            paragraph: 段落
            max_chunk_size: 最大块大小
            min_chunk_size: 最小块大小

        Returns:
            块列表
        """
        chunks = []

        # 按句子分割
        sentences = self._split_by_sentences(paragraph)

        current_chunk = ""
        current_start = 0

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chunk_size:
                current_chunk += sentence
            else:
                if current_chunk and len(current_chunk) >= min_chunk_size:
                    chunks.append(
                        Chunk(
                            content=current_chunk.strip(),
                            start_index=current_start,
                            end_index=current_start + len(current_chunk),
                            chunk_type="semantic",
                            metadata={"method": "sentence"},
                        )
                    )

                current_chunk = sentence
                current_start = chunks[-1].end_index if chunks else 0

        if current_chunk and len(current_chunk) >= min_chunk_size:
            chunks.append(
                Chunk(
                    content=current_chunk.strip(),
                    start_index=current_start,
                    end_index=current_start + len(current_chunk),
                    chunk_type="semantic",
                    metadata={"method": "sentence"},
                )
            )

        return chunks

    def _split_by_sentences(self, text: str) -> list[str]:
        """按句子分割

        Args:
            text: 文本

        Returns:
            句子列表
        """
        # 中英文句子分割
        sentences = re.split(r"([。！？\.!?]+[\s\n]*)", text)

        # 合并句子和标点
        result = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])

        return [s.strip() for s in result if s.strip()]

    async def chunk_by_structure(self, text: str, structure_markers: dict = None) -> list[Chunk]:
        """结构化分块（基于标题、列表等）

        Args:
            text: 文本
            structure_markers: 结构标记

        Returns:
            块列表
        """
        if structure_markers is None:
            structure_markers = {
                "heading": r"^#{1,6}\s+.+$",  # Markdown标题
                "list": r"^[\*\-\+\d\.]\s+.+$",  # 列表项
            }

        chunks = []
        lines = text.split("\n")

        current_chunk = ""
        current_type = "normal"
        current_start = 0

        for line in lines:
            # 检测结构类型
            line_type = "normal"
            for struct_type, pattern in structure_markers.items():
                if re.match(pattern, line.strip(), re.MULTILINE):
                    line_type = struct_type
                    break

            # 如果类型变化，保存当前块
            if line_type != current_type and current_chunk:
                chunks.append(
                    Chunk(
                        content=current_chunk.strip(),
                        start_index=current_start,
                        end_index=current_start + len(current_chunk),
                        chunk_type=current_type,
                        metadata={"method": "structure"},
                    )
                )
                current_chunk = line + "\n"
                current_type = line_type
                current_start = chunks[-1].end_index if chunks else 0
            else:
                current_chunk += line + "\n"

        # 添加最后一块
        if current_chunk:
            chunks.append(
                Chunk(
                    content=current_chunk.strip(),
                    start_index=current_start,
                    end_index=current_start + len(current_chunk),
                    chunk_type=current_type,
                    metadata={"method": "structure"},
                )
            )

        return chunks

    async def chunk_with_overlap(
        self, text: str, chunk_size: int = None, overlap_size: int = None
    ) -> list[Chunk]:
        """固定大小分块（带重叠）

        Args:
            text: 文本
            chunk_size: 块大小
            overlap_size: 重叠大小

        Returns:
            块列表
        """
        if chunk_size is None:
            chunk_size = self.max_chunk_size
        if overlap_size is None:
            overlap_size = self.overlap_size

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # 尝试在句子边界切分
            if end < len(text):
                # 查找最近的句子结束标记
                sentence_ends = [".", "。", "!", "！", "?", "？", "\n"]
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in sentence_ends:
                        end = i + 1
                        break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        start_index=start,
                        end_index=end,
                        chunk_type="fixed",
                        metadata={"method": "fixed_overlap"},
                    )
                )

            # 移动起点（考虑重叠）
            start = end - overlap_size

            # 避免无限循环
            if start >= len(text):
                break

        return chunks

    async def optimize_chunks(
        self, chunks: list[Chunk], min_size: int = None, max_size: int = None
    ) -> list[Chunk]:
        """优化块（合并过小的块，分割过大的块）

        Args:
            chunks: 块列表
            min_size: 最小大小
            max_size: 最大大小

        Returns:
            优化后的块列表
        """
        if min_size is None:
            min_size = self.min_chunk_size
        if max_size is None:
            max_size = self.max_chunk_size

        optimized = []
        i = 0

        while i < len(chunks):
            chunk = chunks[i]

            # 如果太小，尝试与下一块合并
            if len(chunk.content) < min_size and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                if len(chunk.content) + len(next_chunk.content) <= max_size:
                    merged = Chunk(
                        content=chunk.content + "\n\n" + next_chunk.content,
                        start_index=chunk.start_index,
                        end_index=next_chunk.end_index,
                        chunk_type="merged",
                        metadata={"method": "merge"},
                    )
                    optimized.append(merged)
                    i += 2
                    continue

            # 如果太大，分割
            if len(chunk.content) > max_size:
                sub_chunks = await self.chunk_with_overlap(
                    chunk.content, max_size, self.overlap_size
                )
                optimized.extend(sub_chunks)
            else:
                optimized.append(chunk)

            i += 1

        return optimized
