"""
Document Management API

文档管理 API 路由
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"]
)


# Request/Response Models

class UploadDocumentRequest(BaseModel):
    """上传文档请求"""
    knowledge_base_id: str = Field(..., description="知识库 ID")
    name: Optional[str] = Field(None, description="文档名称")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class UploadDocumentResponse(BaseModel):
    """上传文档响应"""
    document_id: str
    file_name: str
    file_size: int
    file_type: str
    status: str
    file_url: Optional[str] = None


class ProcessDocumentRequest(BaseModel):
    """处理文档请求"""
    document_id: str
    chunk_size: Optional[int] = Field(500, description="分块大小")
    chunk_overlap: Optional[int] = Field(50, description="分块重叠")


class ProcessDocumentResponse(BaseModel):
    """处理文档响应"""
    document_id: str
    chunks_count: int
    status: str


class GetDocumentResponse(BaseModel):
    """获取文档响应"""
    document_id: str
    name: str
    file_name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    uploaded_by: str
    created_at: str
    updated_at: str


class ListDocumentsResponse(BaseModel):
    """列出文档响应"""
    documents: List[GetDocumentResponse]
    total: int


# API Endpoints

@router.post("/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_base_id: str = Form(...),
    name: Optional[str] = Form(None),
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    session: AsyncSession = Depends(get_session)
):
    """
    上传文档

    - **file**: 文档文件
    - **knowledge_base_id**: 知识库 ID
    - **name**: 文档显示名称（可选）
    """
    try:
        from app.core.config import settings
        from app.services.document_manager import get_document_manager
        from app.storage.minio_client import get_minio_client

        # 读取文件数据
        file_data = await file.read()

        # 初始化 MinIO 客户端
        minio = get_minio_client(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket_name=settings.MINIO_BUCKET_NAME,
            secure=settings.MINIO_SECURE
        )

        # 初始化文档管理器
        doc_manager = get_document_manager(minio)

        # 上传文档
        document = await doc_manager.upload_document(
            knowledge_base_id=knowledge_base_id,
            file_name=file.filename or "unknown",
            file_data=file_data,
            tenant_id=x_tenant_id,
            uploaded_by=x_user_id,
            name=name
        )

        # 保存到数据库
        repo = DocumentRepository(session)
        await repo.create(document)

        return UploadDocumentResponse(
            document_id=document.id,
            file_name=document.file_name,
            file_size=document.file_size,
            file_type=document.file_type.value,
            status=document.status.value,
            file_url=document.file_url
        )

    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.post("/process", response_model=ProcessDocumentResponse)
async def process_document(
    request: ProcessDocumentRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    处理文档（提取内容并分块）

    - **document_id**: 文档 ID
    - **chunk_size**: 分块大小
    - **chunk_overlap**: 分块重叠
    """
    try:
        from app.core.config import settings
        from app.services.document_manager import get_document_manager
        from app.storage.minio_client import get_minio_client

        # 从数据库获取文档
        repo = DocumentRepository(session)
        document = await repo.get_by_id(request.document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # 初始化 MinIO
        minio = get_minio_client(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket_name=settings.MINIO_BUCKET_NAME,
            secure=settings.MINIO_SECURE
        )
        doc_manager = get_document_manager(minio)

        # 下载文件
        file_data = await doc_manager.download_document(
            request.document_id,
            document.file_path
        )

        # 提取内容
        content = await doc_manager.extract_content(document, file_data)

        # 处理文档
        chunks = await doc_manager.process_document(document, content)

        # 保存块到数据库
        await repo.create_chunks(chunks)

        # 更新文档状态
        await repo.update(document)

        return ProcessDocumentResponse(
            document_id=request.document_id,
            chunks_count=len(chunks),
            status=document.status.value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}"
        )


@router.get("/{document_id}", response_model=GetDocumentResponse)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    获取文档详情

    - **document_id**: 文档 ID
    """
    try:
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        return GetDocumentResponse(
            document_id=document.id,
            name=document.name,
            file_name=document.file_name,
            file_type=document.file_type.value,
            file_size=document.file_size,
            status=document.status.value,
            chunk_count=document.chunk_count,
            uploaded_by=document.uploaded_by,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.get("/", response_model=ListDocumentsResponse)
async def list_documents(
    knowledge_base_id: str,
    offset: int = 0,
    limit: int = 20,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    session: AsyncSession = Depends(get_session)
):
    """
    列出文档

    - **knowledge_base_id**: 知识库 ID
    - **offset**: 偏移量
    - **limit**: 数量限制
    """
    try:
        repo = DocumentRepository(session)
        documents, total = await repo.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            tenant_id=x_tenant_id,
            offset=offset,
            limit=limit
        )

        docs_response = [
            GetDocumentResponse(
                document_id=doc.id,
                name=doc.name,
                file_name=doc.file_name,
                file_type=doc.file_type.value,
                file_size=doc.file_size,
                status=doc.status.value,
                chunk_count=doc.chunk_count,
                uploaded_by=doc.uploaded_by,
                created_at=doc.created_at.isoformat(),
                updated_at=doc.updated_at.isoformat()
            )
            for doc in documents
        ]

        return ListDocumentsResponse(
            documents=docs_response,
            total=total
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    session: AsyncSession = Depends(get_session)
):
    """
    删除文档

    - **document_id**: 文档 ID
    """
    try:
        from app.core.config import settings
        from app.services.document_manager import get_document_manager
        from app.storage.minio_client import get_minio_client

        # 从数据库获取文档
        repo = DocumentRepository(session)
        document = await repo.get_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # 初始化 MinIO
        minio = get_minio_client(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket_name=settings.MINIO_BUCKET_NAME,
            secure=settings.MINIO_SECURE
        )
        doc_manager = get_document_manager(minio)

        # 删除文件
        await doc_manager.delete_document(document_id, document.file_path)

        # 标记删除并更新数据库
        document.mark_deleted()
        await repo.update(document)

        return {"message": "Document deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """
    获取文档下载 URL

    - **document_id**: 文档 ID
    """
    try:
        from app.services.document_manager import get_document_manager
        from app.storage.minio_client import get_minio_client

        # TODO: 从数据库获取文档
        # document = await db.get_document(document_id)

        # 初始化文档管理器
        minio = get_minio_client()
        doc_manager = get_document_manager(minio)

        # 生成下载 URL
        # url = await doc_manager.get_download_url(document.file_path)

        return {
            "download_url": "TODO",
            "expires_in": 3600
        }

    except Exception as e:
        logger.error(f"Failed to get download URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get download URL: {str(e)}"
        )
