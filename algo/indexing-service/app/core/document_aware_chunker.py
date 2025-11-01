"""
文档类型感知分块器
针对不同文档类型实现专用分块策略
"""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ChunkingStrategy(ABC):
    """分块策略基类"""

    @abstractmethod
    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        分块方法

        Args:
            text: 文档文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        pass

    def _generate_chunk_id(self, document_id: str, index: int, text: str) -> str:
        """生成分块 ID"""
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"{document_id}_chunk_{index}_{text_hash}"

    def _estimate_tokens(self, text: str) -> int:
        """估算 Token 数量"""
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
        english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])
        return int(chinese_chars * 1.5 + english_words * 1.3)


class MarkdownChunkStrategy(ChunkingStrategy):
    """Markdown 文档分块策略（按标题层级）"""

    def __init__(
        self,
        max_chunk_size: int = 800,
        keep_hierarchy: bool = True,
    ):
        """
        初始化 Markdown 分块策略

        Args:
            max_chunk_size: 最大块大小
            keep_hierarchy: 是否保留标题层级信息
        """
        self.max_chunk_size = max_chunk_size
        self.keep_hierarchy = keep_hierarchy

    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        按 Markdown 标题切分

        策略:
        1. 识别标题层级 (h1-h6)
        2. 按标题切分内容
        3. 保留标题上下文

        Args:
            text: Markdown 文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        # 按标题分割
        sections = self._split_by_headers(text)

        chunks = []
        for i, section in enumerate(sections):
            # 如果section太大，再次分割
            if len(section["content"]) > self.max_chunk_size:
                sub_chunks = self._split_large_section(section["content"])
                for j, sub_content in enumerate(sub_chunks):
                    chunks.append(
                        {
                            "id": self._generate_chunk_id(document_id, len(chunks), sub_content),
                            "content": sub_content,
                            "index": len(chunks),
                            "tokens": self._estimate_tokens(sub_content),
                            "metadata": {
                                "document_id": document_id,
                                "chunk_index": len(chunks),
                                "chunking_method": "markdown",
                                "header_level": section["level"],
                                "header_text": section["header"],
                                "sub_chunk": j,
                            },
                        }
                    )
            else:
                chunks.append(
                    {
                        "id": self._generate_chunk_id(document_id, i, section["content"]),
                        "content": section["content"],
                        "index": i,
                        "tokens": self._estimate_tokens(section["content"]),
                        "metadata": {
                            "document_id": document_id,
                            "chunk_index": i,
                            "chunking_method": "markdown",
                            "header_level": section["level"],
                            "header_text": section["header"],
                        },
                    }
                )

        return chunks

    def _split_by_headers(self, text: str) -> list[dict[str, Any]]:
        """按标题分割文本"""
        # 匹配 Markdown 标题 (# 到 ######)
        header_pattern = r'^(#{1,6})\s+(.+)$'

        lines = text.split("\n")
        sections = []
        current_section = {"level": 0, "header": "", "content": ""}

        for line in lines:
            match = re.match(header_pattern, line)

            if match:
                # 保存当前section
                if current_section["content"].strip():
                    sections.append(current_section)

                # 开始新section
                level = len(match.group(1))
                header = match.group(2).strip()

                current_section = {
                    "level": level,
                    "header": header,
                    "content": f"{line}\n",  # 包含标题本身
                }
            else:
                current_section["content"] += f"{line}\n"

        # 添加最后一个section
        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _split_large_section(self, content: str) -> list[str]:
        """分割大section"""
        paragraphs = content.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += f"\n\n{para}"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks


class CodeChunkStrategy(ChunkingStrategy):
    """代码文档分块策略（按函数/类）"""

    def __init__(
        self,
        max_chunk_size: int = 1000,
        languages: list[str] | None = None,
    ):
        """
        初始化代码分块策略

        Args:
            max_chunk_size: 最大块大小
            languages: 支持的语言列表
        """
        self.max_chunk_size = max_chunk_size
        self.languages = languages or ["python", "javascript", "typescript", "java", "go"]

    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        按代码结构切分

        策略:
        1. 识别函数、类定义
        2. 按函数/类切分
        3. 保持代码完整性

        Args:
            text: 代码文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        language = metadata.get("language", "python") if metadata else "python"

        # 根据语言选择分割策略
        if language == "python":
            code_blocks = self._split_python_code(text)
        elif language in ["javascript", "typescript"]:
            code_blocks = self._split_javascript_code(text)
        else:
            # 默认按固定大小分割
            code_blocks = self._split_by_lines(text, 50)

        chunks = []
        for i, block in enumerate(code_blocks):
            chunks.append(
                {
                    "id": self._generate_chunk_id(document_id, i, block["content"]),
                    "content": block["content"],
                    "index": i,
                    "tokens": self._estimate_tokens(block["content"]),
                    "metadata": {
                        "document_id": document_id,
                        "chunk_index": i,
                        "chunking_method": "code",
                        "language": language,
                        "block_type": block["type"],
                        "block_name": block.get("name", ""),
                    },
                }
            )

        return chunks

    def _split_python_code(self, text: str) -> list[dict[str, Any]]:
        """分割 Python 代码"""
        blocks = []

        # 匹配类定义
        class_pattern = r'^class\s+(\w+).*?:'
        # 匹配函数定义
        function_pattern = r'^def\s+(\w+).*?:'

        lines = text.split("\n")
        current_block = {"type": "module", "name": "", "content": "", "indent": 0}

        for line in lines:
            # 检查是否是类定义
            class_match = re.match(class_pattern, line)
            if class_match:
                if current_block["content"].strip():
                    blocks.append(current_block)

                current_block = {
                    "type": "class",
                    "name": class_match.group(1),
                    "content": f"{line}\n",
                    "indent": len(line) - len(line.lstrip()),
                }
                continue

            # 检查是否是函数定义
            function_match = re.match(function_pattern, line)
            if function_match:
                indent = len(line) - len(line.lstrip())

                # 如果是同级或外层函数，保存当前块
                if indent <= current_block["indent"] and current_block["type"] in ["function", "method"]:
                    if current_block["content"].strip():
                        blocks.append(current_block)

                    current_block = {
                        "type": "function" if indent == 0 else "method",
                        "name": function_match.group(1),
                        "content": f"{line}\n",
                        "indent": indent,
                    }
                else:
                    current_block["content"] += f"{line}\n"

                continue

            # 普通行
            current_block["content"] += f"{line}\n"

        # 添加最后一个块
        if current_block["content"].strip():
            blocks.append(current_block)

        return blocks

    def _split_javascript_code(self, text: str) -> list[dict[str, Any]]:
        """分割 JavaScript 代码"""
        blocks = []

        # 匹配函数定义
        function_patterns = [
            r'function\s+(\w+)',  # function foo()
            r'const\s+(\w+)\s*=\s*(?:async\s+)?\(',  # const foo = () => {}
            r'let\s+(\w+)\s*=\s*(?:async\s+)?\(',  # let foo = () => {}
            r'var\s+(\w+)\s*=\s*(?:async\s+)?\(',  # var foo = () => {}
        ]

        # 匹配类定义
        class_pattern = r'class\s+(\w+)'

        lines = text.split("\n")
        current_block = {"type": "module", "name": "", "content": ""}

        for line in lines:
            # 检查类定义
            class_match = re.search(class_pattern, line)
            if class_match:
                if current_block["content"].strip():
                    blocks.append(current_block)

                current_block = {
                    "type": "class",
                    "name": class_match.group(1),
                    "content": f"{line}\n",
                }
                continue

            # 检查函数定义
            function_matched = False
            for pattern in function_patterns:
                function_match = re.search(pattern, line)
                if function_match:
                    if current_block["content"].strip():
                        blocks.append(current_block)

                    current_block = {
                        "type": "function",
                        "name": function_match.group(1),
                        "content": f"{line}\n",
                    }
                    function_matched = True
                    break

            if not function_matched:
                current_block["content"] += f"{line}\n"

        # 添加最后一个块
        if current_block["content"].strip():
            blocks.append(current_block)

        return blocks

    def _split_by_lines(self, text: str, lines_per_chunk: int) -> list[dict[str, Any]]:
        """按行数分割"""
        lines = text.split("\n")
        blocks = []

        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i : i + lines_per_chunk]
            blocks.append(
                {
                    "type": "code_block",
                    "name": f"block_{i // lines_per_chunk}",
                    "content": "\n".join(chunk_lines),
                }
            )

        return blocks


class PDFChunkStrategy(ChunkingStrategy):
    """PDF 文档分块策略（按页面和段落）"""

    def __init__(
        self,
        max_chunk_size: int = 800,
        preserve_pages: bool = True,
    ):
        """
        初始化 PDF 分块策略

        Args:
            max_chunk_size: 最大块大小
            preserve_pages: 是否保留页面信息
        """
        self.max_chunk_size = max_chunk_size
        self.preserve_pages = preserve_pages

    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        按页面和段落切分

        Args:
            text: PDF 文本
            document_id: 文档 ID
            metadata: 元数据（包含页面信息）

        Returns:
            分块列表
        """
        # 假设 text 已经包含页面标记（从 PDF 解析器获得）
        # 格式: [PAGE:1]content[PAGE:2]content...

        pages = self._extract_pages(text)

        chunks = []
        for page_num, page_content in pages.items():
            # 按段落分割页面内容
            paragraphs = page_content.split("\n\n")

            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > self.max_chunk_size:
                    if current_chunk:
                        chunks.append(
                            {
                                "id": self._generate_chunk_id(document_id, len(chunks), current_chunk),
                                "content": current_chunk.strip(),
                                "index": len(chunks),
                                "tokens": self._estimate_tokens(current_chunk),
                                "metadata": {
                                    "document_id": document_id,
                                    "chunk_index": len(chunks),
                                    "chunking_method": "pdf",
                                    "page_number": page_num,
                                },
                            }
                        )
                    current_chunk = para
                else:
                    current_chunk += f"\n\n{para}" if current_chunk else para

            # 添加最后一个chunk
            if current_chunk:
                chunks.append(
                    {
                        "id": self._generate_chunk_id(document_id, len(chunks), current_chunk),
                        "content": current_chunk.strip(),
                        "index": len(chunks),
                        "tokens": self._estimate_tokens(current_chunk),
                        "metadata": {
                            "document_id": document_id,
                            "chunk_index": len(chunks),
                            "chunking_method": "pdf",
                            "page_number": page_num,
                        },
                    }
                )

        return chunks

    def _extract_pages(self, text: str) -> dict[int, str]:
        """提取页面内容"""
        # 简单实现：按 [PAGE:N] 标记分割
        page_pattern = r'\[PAGE:(\d+)\]'

        pages = {}
        current_page = 1
        current_content = ""

        for line in text.split("\n"):
            match = re.search(page_pattern, line)
            if match:
                # 保存当前页面
                if current_content.strip():
                    pages[current_page] = current_content.strip()

                # 开始新页面
                current_page = int(match.group(1))
                current_content = line.replace(match.group(0), "")
            else:
                current_content += f"{line}\n"

        # 添加最后一页
        if current_content.strip():
            pages[current_page] = current_content.strip()

        return pages


class TableChunkStrategy(ChunkingStrategy):
    """表格分块策略（保留表格完整性）"""

    async def chunk(
        self,
        text: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        保留表格完整性的分块

        策略:
        1. 识别表格标记
        2. 每个表格作为一个独立chunk
        3. 其他内容按段落切分

        Args:
            text: 文本
            document_id: 文档 ID
            metadata: 元数据

        Returns:
            分块列表
        """
        # 简单实现：识别 Markdown 表格或 CSV 表格
        chunks = []

        # 按段落分割
        blocks = text.split("\n\n")

        for block in blocks:
            # 检查是否是表格（Markdown 表格以 | 开头）
            if self._is_table(block):
                # 表格作为独立 chunk
                chunks.append(
                    {
                        "id": self._generate_chunk_id(document_id, len(chunks), block),
                        "content": block.strip(),
                        "index": len(chunks),
                        "tokens": self._estimate_tokens(block),
                        "metadata": {
                            "document_id": document_id,
                            "chunk_index": len(chunks),
                            "chunking_method": "table",
                            "content_type": "table",
                        },
                    }
                )
            else:
                # 普通文本
                chunks.append(
                    {
                        "id": self._generate_chunk_id(document_id, len(chunks), block),
                        "content": block.strip(),
                        "index": len(chunks),
                        "tokens": self._estimate_tokens(block),
                        "metadata": {
                            "document_id": document_id,
                            "chunk_index": len(chunks),
                            "chunking_method": "table",
                            "content_type": "text",
                        },
                    }
                )

        return chunks

    def _is_table(self, text: str) -> bool:
        """判断是否是表格"""
        lines = text.strip().split("\n")

        # Markdown 表格：大部分行包含 |
        table_line_count = sum(1 for line in lines if "|" in line)

        return table_line_count >= len(lines) * 0.7  # 70% 的行包含 |


class DocumentAwareChunker:
    """文档类型感知分块器"""

    def __init__(self):
        """初始化文档类型感知分块器"""
        self.strategies: dict[str, ChunkingStrategy] = {
            "markdown": MarkdownChunkStrategy(),
            "code": CodeChunkStrategy(),
            "pdf": PDFChunkStrategy(),
            "table": TableChunkStrategy(),
        }

        logger.info(f"DocumentAwareChunker initialized with {len(self.strategies)} strategies")

    async def chunk(
        self,
        text: str,
        document_id: str,
        doc_type: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        根据文档类型选择分块策略

        Args:
            text: 文档文本
            document_id: 文档 ID
            doc_type: 文档类型 (markdown/code/pdf/table/general)
            metadata: 元数据

        Returns:
            分块列表
        """
        # 选择策略
        strategy = self.strategies.get(doc_type)

        if strategy:
            logger.info(f"Using {doc_type} chunking strategy for {document_id}")
            return await strategy.chunk(text, document_id, metadata)

        else:
            # 默认策略：按固定大小切分
            logger.info(f"Using default chunking strategy for {document_id}")
            return await self._default_chunk(text, document_id)

    async def _default_chunk(
        self,
        text: str,
        document_id: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[dict[str, Any]]:
        """默认分块策略（固定大小）"""
        from app.core.chunker import DocumentChunker

        chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=overlap)
        return await chunker.chunk(text, document_id)

    def register_strategy(self, doc_type: str, strategy: ChunkingStrategy):
        """
        注册新的分块策略

        Args:
            doc_type: 文档类型
            strategy: 分块策略实例
        """
        self.strategies[doc_type] = strategy
        logger.info(f"Registered chunking strategy for {doc_type}")
