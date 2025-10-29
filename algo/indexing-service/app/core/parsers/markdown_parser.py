"""Markdown 解析器"""

import logging

from app.core.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class MarkdownParser(BaseParser):
    """Markdown 文档解析器"""

    async def parse(self, file_data: bytes, **kwargs) -> str:
        """解析 Markdown 文档"""
        try:
            # Markdown 是纯文本，直接解码
            text = file_data.decode("utf-8")
            return self.clean_text(text)
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                text = file_data.decode("gbk")
                return self.clean_text(text)
            except:
                logger.error("Failed to decode Markdown file")
                raise
