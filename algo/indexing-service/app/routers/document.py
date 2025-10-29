"""文档处理路由"""
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.document_service import DocumentService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
document_service = DocumentService()


class IndexDocumentRequest(BaseModel):
    """索引文档请求"""
    document_id: str = Field(..., description="文档ID")
    tenant_id: str = Field(..., description="租户ID")
    knowledge_base_id: str = Field(..., description="知识库ID")
    options: dict[str, Any] = Field(default_factory=dict, description="索引选项")


class IndexDocumentResponse(BaseModel):
    """索引文档响应"""
    job_id: str
    document_id: str
    status: str
    message: str


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = "",
    knowledge_base_id: str = "",
):
    """
    上传文档

    支持的格式: PDF, DOCX, TXT, MD, HTML
    """
    try:
        # 验证文件格式
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ["pdf", "docx", "txt", "md", "html"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_extension}"
            )

        # 读取文件内容
        content = await file.read()

        # 保存文档
        document = await document_service.save_document(
            filename=file.filename,
            content=content,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
        )

        logger.info(f"Document uploaded: {document['id']}")

        return {
            "document_id": document["id"],
            "filename": file.filename,
            "size": len(content),
            "status": "uploaded",
        }

    except Exception as e:
        logger.error(f"Failed to upload document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index", response_model=IndexDocumentResponse)
async def index_document(
    request: IndexDocumentRequest,
    background_tasks: BackgroundTasks,
):
    """
    索引文档（异步）

    执行流程:
    1. 解析文档内容
    2. 文本分块（Chunking）
    3. 向量化（Embedding）
    4. 存储到Milvus
    5. 构建知识图谱（Neo4j）
    """
    try:
        # 创建索引任务
        job_id = await document_service.create_indexing_job(
            document_id=request.document_id,
            tenant_id=request.tenant_id,
            knowledge_base_id=request.knowledge_base_id,
            options=request.options,
        )

        # 添加后台任务
        background_tasks.add_task(
            document_service.process_document,
            document_id=request.document_id,
            job_id=job_id,
            options=request.options,
        )

        logger.info(f"Indexing job created: {job_id} for document {request.document_id}")

        return IndexDocumentResponse(
            job_id=job_id,
            document_id=request.document_id,
            status="pending",
            message="Indexing job submitted successfully",
        )

    except Exception as e:
        logger.error(f"Failed to create indexing job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/{job_id}")
async def get_indexing_status(job_id: str):
    """获取索引任务状态"""
    try:
        status = await document_service.get_job_status(job_id)

        if not status:
            raise HTTPException(status_code=404, detail="Job not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    删除文档及其索引

    包括:
    - 文档元数据
    - 文本块
    - 向量索引
    - 知识图谱节点
    """
    try:
        await document_service.delete_document(document_id)

        logger.info(f"Document deleted: {document_id}")

        return {
            "document_id": document_id,
            "status": "deleted",
        }

    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
