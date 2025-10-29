"""HTML 解析器"""

import logging

from bs4 import BeautifulSoup

from app.core.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class HTMLParser(BaseParser):
    """HTML 文档解析器"""

    async def parse(self, file_data: bytes, **kwargs) -> str:
        """解析 HTML 文档"""
        try:
            soup = BeautifulSoup(file_data, "html.parser")

            # 移除 script 和 style 标签
            for script in soup(["script", "style"]):
                script.decompose()

            # 提取文本
            text = soup.get_text()

            # 清理空行
            lines = (line.strip() for line in text.splitlines())
            text = "\n".join(line for line in lines if line)

            return self.clean_text(text)

        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            raise
