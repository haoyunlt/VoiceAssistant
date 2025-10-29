"""
Document Management Service

文档管理服务，负责文档的上传、处理、存储和检索
"""

import asyncio
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.document import Chunk, Document, DocumentStatus, DocumentType
from app.storage.minio_client import MinIOClient

logger = logging.getLogger(__name__)


class DocumentManager:
    """文档管理器"""

    def __init__(
        self,
        minio_client: MinIOClient,
        # virus_scanner: Optional['VirusScanner'] = None,  # 可选病毒扫描
        # db_repo: Optional['DocumentRepository'] = None    # 可选数据库存储
    ):
        """初始化文档管理器

        Args:
            minio_client: MinIO 存储客户端
        """
        self.minio = minio_client
        # self.virus_scanner = virus_scanner
        # self.db_repo = db_repo

    async def upload_document(
        self,
        knowledge_base_id: str,
        file_name: str,
        file_data: bytes,
        tenant_id: str,
        uploaded_by: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        """上传文档

        Args:
            knowledge_base_id: 知识库 ID
            file_name: 文件名
            file_data: 文件数据
            tenant_id: 租户 ID
            uploaded_by: 上传者 ID
            name: 显示名称
            metadata: 元数据

        Returns:
            文档对象
        """
        # 确定文档类型
        file_type = self._determine_file_type(file_name)

        # 创建文档对象
        doc = Document.create(
            knowledge_base_id=knowledge_base_id,
            name=name or file_name,
            file_name=file_name,
            file_type=file_type,
            file_size=len(file_data),
            file_path=f"{tenant_id}/{knowledge_base_id}/{datetime.utcnow().strftime('%Y%m%d')}/{file_name}",
            tenant_id=tenant_id,
            uploaded_by=uploaded_by
        )

        if metadata:
            doc.update(metadata=metadata)

        # 病毒扫描（可选）
        # if self.virus_scanner:
        #     is_clean, virus_name = await self.virus_scanner.scan(file_data)
        #     if not is_clean:
        #         doc.mark_infected(virus_name)
        #         logger.warning(f"Document {doc.id} infected with {virus_name}")
        #         return doc

        # 上传到 MinIO
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        await self.minio.upload_file(doc.file_path, file_data, content_type)

        # 生成访问 URL
        url = await self.minio.get_presigned_url(doc.file_path, expires=timedelta(days=7))
        doc.set_file_url(url)

        # 保存到数据库（可选）
        # if self.db_repo:
        #     await self.db_repo.save(doc)

        logger.info(f"Uploaded document: {doc.id}")
        return doc

    async def download_document(self, document_id: str, file_path: str) -> bytes:
        """下载文档

        Args:
            document_id: 文档 ID
            file_path: 文件路径

        Returns:
            文件数据
        """
        data = await self.minio.download_file(file_path)
        logger.info(f"Downloaded document: {document_id}")
        return data

    async def delete_document(self, document_id: str, file_path: str) -> None:
        """删除文档

        Args:
            document_id: 文档 ID
            file_path: 文件路径
        """
        await self.minio.delete_file(file_path)
        logger.info(f"Deleted document: {document_id}")

    async def get_download_url(self, file_path: str, expires: timedelta = timedelta(hours=1)) -> str:
        """获取下载 URL

        Args:
            file_path: 文件路径
            expires: 过期时间

        Returns:
            下载 URL
        """
        return await self.minio.get_presigned_url(file_path, expires)

    def _determine_file_type(self, file_name: str) -> DocumentType:
        """确定文件类型

        Args:
            file_name: 文件名

        Returns:
            文档类型
        """
        ext = file_name.lower().split('.')[-1]
        type_map = {
            'pdf': DocumentType.PDF,
            'doc': DocumentType.WORD,
            'docx': DocumentType.WORD,
            'md': DocumentType.MARKDOWN,
            'markdown': DocumentType.MARKDOWN,
            'html': DocumentType.HTML,
            'htm': DocumentType.HTML,
            'json': DocumentType.JSON,
            'txt': DocumentType.TEXT,
        }
        return type_map.get(ext, DocumentType.TEXT)

    async def process_document(self, document: Document, content: str) -> List[Chunk]:
        """处理文档（分块）

        Args:
            document: 文档对象
            content: 文档内容

        Returns:
            文档块列表
        """
        document.start_processing()
        document.set_content(content)

        try:
            # 分块
            chunks = await self._chunk_document(document, content)
            document.complete_processing(len(chunks))
            logger.info(f"Processed document {document.id}: {len(chunks)} chunks")
            return chunks
        except Exception as e:
            document.fail_processing(str(e))
            logger.error(f"Failed to process document {document.id}: {e}")
            raise

    async def _chunk_document(
        self,
        document: Document,
        content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> List[Chunk]:
        """文档分块

        Args:
            document: 文档对象
            content: 文档内容
            chunk_size: 块大小（字符）
            chunk_overlap: 重叠大小

        Returns:
            文档块列表
        """
        chunks = []
        start = 0
        sequence = 0

        while start < len(content):
            end = start + chunk_size
            chunk_content = content[start:end]

            chunk = Chunk.create(
                document_id=document.id,
                knowledge_base_id=document.knowledge_base_id,
                content=chunk_content,
                sequence=sequence,
                metadata={
                    "start": start,
                    "end": end,
                    "file_name": document.file_name
                }
            )
            chunks.append(chunk)

            start = end - chunk_overlap
            sequence += 1

        return chunks

    async def extract_content(self, document: Document, file_data: bytes) -> str:
        """提取文档内容

        Args:
            document: 文档对象
            file_data: 文件数据

        Returns:
            文档内容
        """
        if document.file_type == DocumentType.TEXT:
            return file_data.decode('utf-8')
        elif document.file_type == DocumentType.PDF:
            return await self._extract_pdf(file_data)
        elif document.file_type == DocumentType.WORD:
            return await self._extract_docx(file_data)
        elif document.file_type == DocumentType.HTML:
            return await self._extract_html(file_data)
        elif document.file_type == DocumentType.JSON:
            return file_data.decode('utf-8')
        else:
            return file_data.decode('utf-8', errors='ignore')

    async def _extract_pdf(self, file_data: bytes) -> str:
        """提取 PDF 内容

        使用 PyPDF2 或 pdfplumber
        """
        try:
            import io
            from PyPDF2 import PdfReader

            pdf_file = io.BytesIO(file_data)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract PDF: {e}")
            return ""

    async def _extract_docx(self, file_data: bytes) -> str:
        """提取 DOCX 内容

        使用 python-docx
        """
        try:
            import io
            from docx import Document as DocxDocument

            docx_file = io.BytesIO(file_data)
            doc = DocxDocument(docx_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"Failed to extract DOCX: {e}")
            return ""

    async def _extract_html(self, file_data: bytes) -> str:
        """提取 HTML 内容

        使用 BeautifulSoup
        """
        try:
            from bs4 import BeautifulSoup

            html = file_data.decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            return text
        except Exception as e:
            logger.error(f"Failed to extract HTML: {e}")
            return ""


# 全局单例
_document_manager: Optional[DocumentManager] = None


def get_document_manager(minio_client: Optional[MinIOClient] = None) -> DocumentManager:
    """获取文档管理器单例

    Args:
        minio_client: MinIO 客户端

    Returns:
        文档管理器实例
    """
    global _document_manager

    if _document_manager is None:
        if minio_client is None:
            raise ValueError("Document manager not initialized. Provide MinIO client.")
        _document_manager = DocumentManager(minio_client)

    return _document_manager
