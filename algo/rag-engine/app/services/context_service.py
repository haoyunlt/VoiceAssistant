"""上下文组装服务"""
import logging
from typing import List

from app.models.rag import RetrievedDocument

logger = logging.getLogger(__name__)


class ContextService:
    """上下文组装服务"""

    async def build_context(
        self, documents: List[RetrievedDocument], max_length: int = 4000
    ) -> str:
        """
        组装上下文

        Args:
            documents: 检索到的文档
            max_length: 最大长度（字符数）

        Returns:
            组装后的上下文
        """
        if not documents:
            return ""

        context_parts = []
        current_length = 0

        for i, doc in enumerate(documents):
            # 格式化文档
            doc_text = f"[文档 {i+1}]\n{doc.content}\n"
            doc_length = len(doc_text)

            # 检查是否超过最大长度
            if current_length + doc_length > max_length:
                # 尝试截断当前文档
                remaining = max_length - current_length
                if remaining > 100:  # 至少保留100字符
                    doc_text = f"[文档 {i+1}]\n{doc.content[:remaining-20]}...\n"
                    context_parts.append(doc_text)
                break

            context_parts.append(doc_text)
            current_length += doc_length

        context = "\n".join(context_parts)
        logger.info(f"Built context: {len(context)} chars from {len(context_parts)} documents")

        return context
