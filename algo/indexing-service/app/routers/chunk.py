"""文本块管理路由"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.chunk_service import ChunkService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建服务实例
chunk_service = ChunkService()


@router.get("/{document_id}")
async def get_document_chunks(
    document_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """获取文档的所有文本块"""
    try:
        chunks = await chunk_service.get_chunks_by_document(
            document_id=document_id,
            offset=offset,
            limit=limit,
        )

        return {
            "document_id": document_id,
            "chunks": chunks,
            "offset": offset,
            "limit": limit,
            "total": len(chunks),
        }

    except Exception as e:
        logger.error(f"Failed to get chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunk/{chunk_id}")
async def get_chunk(chunk_id: str):
    """获取单个文本块详情"""
    try:
        chunk = await chunk_service.get_chunk_by_id(chunk_id)

        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")

        return chunk

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/{document_id}")
async def reindex_chunks(document_id: str):
    """
    重新索引文档的所有文本块

    用于:
    - 更新向量表示
    - 修复索引错误
    - 切换Embedding模型后重建
    """
    try:
        result = await chunk_service.reindex_document(document_id)

        logger.info(f"Document reindexed: {document_id}")

        return {
            "document_id": document_id,
            "status": "reindexed",
            "chunks_count": result.get("chunks_count", 0),
        }

    except Exception as e:
        logger.error(f"Failed to reindex document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
