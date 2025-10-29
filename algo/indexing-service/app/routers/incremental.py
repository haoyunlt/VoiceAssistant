"""
增量索引 API路由
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/incremental", tags=["Incremental Indexing"])

# 全局服务实例（延迟初始化）
incremental_service = None


async def get_incremental_service():
    """获取或初始化增量索引服务"""
    global incremental_service

    if incremental_service is None:
        logger.info("Initializing IncrementalIndexService...")
        import redis.asyncio as redis

        from app.services.incremental_index_service import IncrementalIndexService

        # 初始化Redis客户端
        redis_client = redis.from_url("redis://localhost:6379/0")

        incremental_service = IncrementalIndexService(
            redis_client=redis_client, version_ttl=604800  # 7天
        )
        logger.info("IncrementalIndexService initialized")

    return incremental_service


class DetectChangesRequest(BaseModel):
    """检测变更请求"""

    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")
    chunks: list[str] = Field(..., description="分块列表")


class BulkCheckRequest(BaseModel):
    """批量检查请求"""

    documents: list[dict] = Field(
        ..., description="文档列表，每个文档包含 {id, content}"
    )


class IncrementalUpdateRequest(BaseModel):
    """增量更新请求"""

    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="文档内容")
    chunks: list[str] = Field(..., description="分块列表")
    metadata: dict | None = Field(None, description="元数据")


@router.post("/detect-changes")
async def detect_changes(request: DetectChangesRequest):
    """
    检测文档变更

    对比新文档与已索引版本，检测内容和分块级别的变更。

    示例:
    ```json
    {
        "document_id": "doc_123",
        "content": "更新后的文档内容",
        "chunks": ["分块1", "分块2", "分块3"]
    }
    ```

    返回:
    - is_new: 是否为新文档
    - has_changes: 是否有变更
    - new_chunks: 新增分块索引
    - updated_chunks: 更新分块索引
    - deleted_chunks: 删除分块索引
    - change_summary: 变更摘要
    """
    service = await get_incremental_service()

    try:
        changes = await service.detect_changes(
            document_id=request.document_id,
            new_content=request.content,
            new_chunks=request.chunks,
        )

        return changes

    except Exception as e:
        logger.error(f"Failed to detect changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def incremental_update(request: IncrementalUpdateRequest):
    """
    增量更新文档索引

    只更新变更的部分，提高索引效率。

    特性:
    - 内容哈希对比
    - 分块级别差异检测
    - 原子更新操作
    - 版本管理（7天TTL）

    示例:
    ```json
    {
        "document_id": "doc_123",
        "content": "更新后的文档内容",
        "chunks": ["分块1", "分块2", "分块3"],
        "metadata": {"title": "文档标题"}
    }
    ```

    返回:
    - success: 是否成功
    - action: 操作类型（updated/skipped/failed）
    - changes: 变更摘要
    - elapsed_time: 耗时
    """
    service = await get_incremental_service()

    try:
        # TODO: 集成实际的vector_service
        # 这里需要从依赖注入或全局获取vector_service
        from app.services.vector_service import VectorService

        vector_service = VectorService()

        result = await service.incremental_update(
            document_id=request.document_id,
            new_content=request.content,
            new_chunks=request.chunks,
            vector_service=vector_service,
            metadata=request.metadata,
        )

        return result

    except Exception as e:
        logger.error(f"Incremental update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-check")
async def bulk_check_changes(request: BulkCheckRequest):
    """
    批量检查文档变更

    快速检查多个文档的变更状态（不执行实际更新）。

    示例:
    ```json
    {
        "documents": [
            {"id": "doc_1", "content": "内容1"},
            {"id": "doc_2", "content": "内容2"}
        ]
    }
    ```

    返回:
    - 每个文档的状态：new/unchanged/changed
    - 内容哈希对比
    """
    service = await get_incremental_service()

    try:
        results = await service.bulk_check_changes(documents=request.documents)
        return {"results": results, "total": len(results)}

    except Exception as e:
        logger.error(f"Bulk check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version/{document_id}")
async def get_document_version(document_id: str):
    """
    获取文档版本信息

    参数:
    - **document_id**: 文档ID

    返回:
    - content_hash: 内容哈希
    - chunk_hashes: 分块哈希列表
    - indexed_at: 索引时间
    - version: 版本号
    """
    service = await get_incremental_service()

    try:
        version = await service.get_document_version(document_id)

        if not version:
            raise HTTPException(
                status_code=404, detail=f"Document {document_id} not found"
            )

        return version

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics():
    """
    获取增量索引统计信息

    返回:
    - total_versions: 已索引文档数量
    - ttl_seconds: 版本信息保留时长
    """
    service = await get_incremental_service()

    try:
        stats = await service.get_statistics()
        return stats

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
