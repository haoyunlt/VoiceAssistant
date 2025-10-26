"""
文档解析器模块

支持的格式：
- PDF
- Word (DOCX, DOC)
- Markdown
- Excel (XLSX, XLS)
- PowerPoint (PPTX, PPT)
- HTML
- 纯文本 (TXT)
"""

import logging
from pathlib import Path
from typing import Optional

from .base import BaseParser
from .excel_parser import ExcelParser
from .html_parser import HTMLParser
from .markdown_parser import MarkdownParser
from .pdf_parser import PDFParser
from .ppt_parser import PowerPointParser
from .text_parser import TextParser
from .word_parser import WordParser

logger = logging.getLogger(__name__)


class ParserFactory:
    """解析器工厂"""

    def __init__(self):
        """初始化工厂"""
        self._parsers = {
            # PDF
            ".pdf": PDFParser,

            # Word
            ".docx": WordParser,
            ".doc": WordParser,

            # Markdown
            ".md": MarkdownParser,
            ".markdown": MarkdownParser,

            # Excel
            ".xlsx": ExcelParser,
            ".xls": ExcelParser,

            # PowerPoint
            ".pptx": PowerPointParser,
            ".ppt": PowerPointParser,

            # HTML
            ".html": HTMLParser,
            ".htm": HTMLParser,

            # 纯文本
            ".txt": TextParser,
        }

        logger.info(f"Parser factory initialized with {len(self._parsers)} parsers")

    def get_parser(self, file_path: str) -> BaseParser:
        """根据文件扩展名获取解析器"""
        # 提取文件扩展名
        ext = Path(file_path).suffix.lower()

        # 获取解析器类
        parser_cls = self._parsers.get(ext)

        if parser_cls is None:
            logger.warning(f"No parser found for extension: {ext}, using TextParser")
            parser_cls = TextParser

        # 创建解析器实例
        return parser_cls()

    def register_parser(self, extension: str, parser_cls: type):
        """注册自定义解析器"""
        if not extension.startswith("."):
            extension = f".{extension}"

        self._parsers[extension.lower()] = parser_cls
        logger.info(f"Registered parser for extension: {extension}")

    def get_supported_extensions(self) -> list:
        """获取支持的文件扩展名列表"""
        return list(self._parsers.keys())


__all__ = [
    "ParserFactory",
    "BaseParser",
    "PDFParser",
    "WordParser",
    "MarkdownParser",
    "ExcelParser",
    "PowerPointParser",
    "HTMLParser",
    "TextParser",
]
