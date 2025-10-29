"""PDF 解析器"""

import io
import logging

import pdfplumber
import PyPDF2

from app.core.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """PDF 文档解析器"""

    async def parse(self, file_data: bytes, **kwargs) -> str:
        """解析 PDF 文档"""
        try:
            # 优先使用 pdfplumber（更准确）
            text = await self._parse_with_pdfplumber(file_data)

            if not text or len(text) < 100:
                # 降级使用 PyPDF2
                logger.warning("pdfplumber failed or returned too little text, trying PyPDF2")
                text = await self._parse_with_pypdf2(file_data)

            return self.clean_text(text)

        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise

    async def _parse_with_pdfplumber(self, file_data: bytes) -> str:
        """使用 pdfplumber 解析"""
        text_parts = []

        with pdfplumber.open(io.BytesIO(file_data)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        return "\n\n".join(text_parts)

    async def _parse_with_pypdf2(self, file_data: bytes) -> str:
        """使用 PyPDF2 解析"""
        text_parts = []

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))

        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        return "\n\n".join(text_parts)

    def extract_metadata(self, file_data: bytes) -> dict:
        """提取 PDF 元数据"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            metadata = pdf_reader.metadata

            return {
                "title": metadata.get("/Title", ""),
                "author": metadata.get("/Author", ""),
                "subject": metadata.get("/Subject", ""),
                "creator": metadata.get("/Creator", ""),
                "producer": metadata.get("/Producer", ""),
                "pages": len(pdf_reader.pages),
            }
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")
            return {}
