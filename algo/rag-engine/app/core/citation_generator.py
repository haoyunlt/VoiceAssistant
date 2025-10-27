"""引用来源生成器 - 为答案添加引用."""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CitationGenerator:
    """引用来源生成器."""

    def __init__(self, citation_format: str = "inline"):
        """
        初始化引用生成器.

        Args:
            citation_format: 引用格式 (inline/footnote/both)
        """
        self.citation_format = citation_format

    def extract_citations(self, answer: str) -> List[int]:
        """
        从答案中提取引用标记.

        提取形如 [Source N] 的引用。

        Args:
            answer: 答案文本

        Returns:
            引用的source编号列表
        """
        pattern = r'\[Source (\d+)\]'
        matches = re.findall(pattern, answer)
        return [int(m) for m in matches]

    def generate_citations(
        self,
        chunks: List[Dict[str, Any]],
        answer: str,
        include_all: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        生成引用列表.

        Args:
            chunks: 使用的分块列表
            answer: 生成的答案
            include_all: 是否包含所有分块 (False则只包含答案中引用的)

        Returns:
            引用列表，每个引用包含:
            - source_id: 引用ID
            - content: 原文内容
            - metadata: 元数据
            - url: 下载链接 (如果有)
        """
        if include_all:
            cited_indices = list(range(len(chunks)))
        else:
            cited_indices = self.extract_citations(answer)

        citations = []

        for i, idx in enumerate(cited_indices, 1):
            # 注意: idx是1-based，chunks是0-based
            if 0 <= idx - 1 < len(chunks):
                chunk = chunks[idx - 1]
                metadata = chunk.get("metadata", {})

                citation = {
                    "source_id": i,
                    "chunk_id": chunk.get("chunk_id"),
                    "content": chunk.get("content", ""),
                    "score": chunk.get("score", 0),
                    "document_id": metadata.get("document_id"),
                    "filename": metadata.get("filename"),
                    "page": metadata.get("page"),
                    "url": metadata.get("url"),
                }

                citations.append(citation)

        return citations

    def format_citations(
        self,
        citations: List[Dict[str, Any]],
        format_type: str = "markdown",
    ) -> str:
        """
        格式化引用列表为可读文本.

        Args:
            citations: 引用列表
            format_type: 格式类型 (markdown/html/plain)

        Returns:
            格式化后的引用文本
        """
        if not citations:
            return ""

        if format_type == "markdown":
            return self._format_markdown(citations)
        elif format_type == "html":
            return self._format_html(citations)
        else:
            return self._format_plain(citations)

    def _format_markdown(self, citations: List[Dict[str, Any]]) -> str:
        """Markdown格式."""
        lines = ["## Sources\n"]

        for citation in citations:
            source_id = citation["source_id"]
            filename = citation.get("filename", "Unknown")
            page = citation.get("page")

            line = f"**[{source_id}]** {filename}"

            if page:
                line += f" (Page {page})"

            if citation.get("url"):
                line += f" - [View]({citation['url']})"

            lines.append(line)

        return "\n".join(lines)

    def _format_html(self, citations: List[Dict[str, Any]]) -> str:
        """HTML格式."""
        lines = ["<div class='citations'>", "<h3>Sources</h3>", "<ol>"]

        for citation in citations:
            filename = citation.get("filename", "Unknown")
            page = citation.get("page")
            url = citation.get("url")

            item = f"<li>{filename}"

            if page:
                item += f" (Page {page})"

            if url:
                item += f" <a href='{url}' target='_blank'>View</a>"

            item += "</li>"
            lines.append(item)

        lines.extend(["</ol>", "</div>"])
        return "\n".join(lines)

    def _format_plain(self, citations: List[Dict[str, Any]]) -> str:
        """纯文本格式."""
        lines = ["Sources:"]

        for citation in citations:
            source_id = citation["source_id"]
            filename = citation.get("filename", "Unknown")
            page = citation.get("page")

            line = f"[{source_id}] {filename}"

            if page:
                line += f" (Page {page})"

            lines.append(line)

        return "\n".join(lines)

    def add_inline_citations(
        self,
        answer: str,
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        在答案中添加内联引用.

        使用简单启发式: 为每个句子添加最相关的引用。

        Args:
            answer: 原始答案
            chunks: 分块列表

        Returns:
            带引用的答案
        """
        # 简单实现: 在每个句子末尾添加 [Source N]
        # 更复杂的实现可以使用语义相似度匹配

        sentences = re.split(r'([.!?])\s+', answer)

        result = []
        chunk_idx = 0

        for i, part in enumerate(sentences):
            result.append(part)

            # 如果是句子结束标记，添加引用
            if part in ['.', '!', '?'] and chunks:
                # 轮流引用不同的source
                source_id = (chunk_idx % len(chunks)) + 1
                result.append(f" [Source {source_id}]")
                chunk_idx += 1

        return ''.join(result)

    def generate_response_with_citations(
        self,
        answer: str,
        chunks: List[Dict[str, Any]],
        include_inline: bool = False,
        citation_format: str = "markdown",
    ) -> Dict[str, Any]:
        """
        生成带引用的完整响应.

        Args:
            answer: 答案文本
            chunks: 使用的分块列表
            include_inline: 是否添加内联引用
            citation_format: 引用格式

        Returns:
            完整响应字典:
            - answer: 答案文本 (可能包含内联引用)
            - citations: 引用列表
            - formatted_citations: 格式化的引用文本
        """
        # 1. 可选: 添加内联引用
        if include_inline and not self.extract_citations(answer):
            answer = self.add_inline_citations(answer, chunks)

        # 2. 生成引用列表
        citations = self.generate_citations(chunks, answer)

        # 3. 格式化引用
        formatted_citations = self.format_citations(citations, citation_format)

        return {
            "answer": answer,
            "citations": citations,
            "formatted_citations": formatted_citations,
        }
