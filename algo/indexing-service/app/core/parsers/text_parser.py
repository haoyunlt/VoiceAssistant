"""纯文本解析器"""

import logging

from app.core.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """纯文本解析器"""

    async def parse(self, file_data: bytes, **_kwargs) -> str:
        """解析纯文本文档"""
        try:
            # 尝试 UTF-8
            return file_data.decode("utf-8")
        except UnicodeDecodeError:
            # 尝试 GBK
            try:
                return file_data.decode("gbk")
            except UnicodeDecodeError:
                # 尝试 Latin-1
                try:
                    return file_data.decode("latin-1")
                except Exception as e:
                    logger.error(f"Failed to decode text file: {e}")
                    raise
