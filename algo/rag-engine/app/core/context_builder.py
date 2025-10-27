"""上下文构建器 - Token截断, Prompt模板."""

import logging
from typing import Any, Dict, List, Optional

import tiktoken

logger = logging.getLogger(__name__)


class ContextBuilder:
    """上下文构建器."""

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        max_context_tokens: int = 3000,
        chunk_delimiter: str = "\n\n---\n\n",
    ):
        """
        初始化上下文构建器.

        Args:
            model: 用于计算token的模型
            max_context_tokens: 最大上下文token数
            chunk_delimiter: 分块分隔符
        """
        self.model = model
        self.max_context_tokens = max_context_tokens
        self.chunk_delimiter = chunk_delimiter

        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型不支持，使用默认tokenizer
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        计算文本token数.

        Args:
            text: 文本

        Returns:
            Token数量
        """
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Failed to count tokens: {e}")
            # 粗略估算: 1 token ≈ 4 字符
            return len(text) // 4

    def truncate_chunks(
        self,
        chunks: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        截断分块列表以适应token限制.

        优先保留高分数的chunks。

        Args:
            chunks: 检索到的分块列表
            max_tokens: 最大token数 (默认使用max_context_tokens)

        Returns:
            截断后的分块列表
        """
        if not chunks:
            return []

        max_tokens = max_tokens or self.max_context_tokens

        # 按分数排序 (降序)
        sorted_chunks = sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)

        selected_chunks = []
        current_tokens = 0

        for chunk in sorted_chunks:
            content = chunk.get("content", "")
            chunk_tokens = self.count_tokens(content)

            # 如果加上这个chunk会超过限制，则停止
            if current_tokens + chunk_tokens > max_tokens:
                # 如果是第一个chunk且超过限制，截断内容
                if not selected_chunks:
                    truncated_content = self._truncate_text(content, max_tokens)
                    chunk_copy = chunk.copy()
                    chunk_copy["content"] = truncated_content
                    chunk_copy["truncated"] = True
                    selected_chunks.append(chunk_copy)
                break

            selected_chunks.append(chunk)
            current_tokens += chunk_tokens

        return selected_chunks

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """
        截断单个文本以适应token限制.

        Args:
            text: 文本
            max_tokens: 最大token数

        Returns:
            截断后的文本
        """
        try:
            tokens = self.tokenizer.encode(text)
            if len(tokens) <= max_tokens:
                return text

            truncated_tokens = tokens[:max_tokens]
            truncated_text = self.tokenizer.decode(truncated_tokens)
            return truncated_text + "..."

        except Exception as e:
            logger.error(f"Failed to truncate text: {e}")
            # 粗略截断
            estimated_chars = max_tokens * 4
            return text[:estimated_chars] + "..."

    def build_context(
        self,
        chunks: List[Dict[str, Any]],
        include_metadata: bool = True,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        构建上下文字符串.

        Args:
            chunks: 检索到的分块列表
            include_metadata: 是否包含元数据
            max_tokens: 最大token数

        Returns:
            上下文字符串
        """
        # 1. 截断chunks
        selected_chunks = self.truncate_chunks(chunks, max_tokens)

        if not selected_chunks:
            return ""

        # 2. 构建上下文
        context_parts = []

        for i, chunk in enumerate(selected_chunks, 1):
            content = chunk.get("content", "")

            if include_metadata:
                metadata = chunk.get("metadata", {})
                source_info = self._format_metadata(metadata)
                chunk_text = f"[Source {i}]{source_info}\n{content}"
            else:
                chunk_text = content

            context_parts.append(chunk_text)

        context = self.chunk_delimiter.join(context_parts)
        return context

    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        格式化元数据为可读字符串.

        Args:
            metadata: 元数据字典

        Returns:
            格式化后的字符串
        """
        parts = []

        if "filename" in metadata:
            parts.append(f"File: {metadata['filename']}")

        if "page" in metadata:
            parts.append(f"Page: {metadata['page']}")

        if "section" in metadata:
            parts.append(f"Section: {metadata['section']}")

        if parts:
            return " (" + ", ".join(parts) + ")"
        return ""

    def build_prompt(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
        include_instructions: bool = True,
    ) -> List[Dict[str, str]]:
        """
        构建完整的Prompt消息列表.

        Args:
            query: 用户查询
            context: 上下文
            system_prompt: 自定义系统提示
            include_instructions: 是否包含答案指令

        Returns:
            OpenAI消息列表格式
        """
        # 默认系统提示
        if system_prompt is None:
            system_prompt = """You are a helpful AI assistant. Answer the user's question based on the provided context.

Rules:
1. Answer based only on the provided context
2. If the context doesn't contain enough information, say so
3. Cite sources using [Source N] format
4. Be concise and accurate
5. Use the same language as the user's question"""

        messages = [{"role": "system", "content": system_prompt}]

        # 构建用户消息
        if context:
            user_content = f"""Context:
{context}

Question: {query}"""

            if include_instructions:
                user_content += "\n\nPlease answer the question based on the context above."
        else:
            user_content = query

        messages.append({"role": "user", "content": user_content})

        return messages

    def estimate_prompt_tokens(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None,
    ) -> int:
        """
        估算完整prompt的token数.

        Args:
            query: 用户查询
            context: 上下文
            system_prompt: 系统提示

        Returns:
            预估token数
        """
        messages = self.build_prompt(query, context, system_prompt)
        total_text = "\n".join([msg["content"] for msg in messages])
        return self.count_tokens(total_text)
