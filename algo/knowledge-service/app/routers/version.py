"""
Version Management API

版本管理 API 路由
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.repositories.version_repository import VersionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/versions", tags=["versions"])


# Request/Response Models


class CreateVersionRequest(BaseModel):
    """创建版本请求"""

    knowledge_base_id: str = Field(..., description="知识库 ID")
    description: str | None = Field("", description="版本描述")


class VersionSnapshotResponse(BaseModel):
    """版本快照响应"""

    document_count: int
    chunk_count: int
    entity_count: int
    relation_count: int
    vector_index_hash: str
    graph_snapshot_id: str
    created_at: str


class VersionResponse(BaseModel):
    """版本响应"""

    id: str
    knowledge_base_id: str
    version: int
    snapshot: VersionSnapshotResponse
    description: str
    created_by: str
    tenant_id: str
    created_at: str


class ListVersionsResponse(BaseModel):
    """列出版本响应"""

    versions: list[VersionResponse]
    total: int


class RollbackRequest(BaseModel):
    """回滚请求"""

    version_id: str = Field(..., description="目标版本 ID")


# API Endpoints


@router.post("/", response_model=VersionResponse)
async def create_version(
    request: CreateVersionRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    x_user_id: str = Header("anonymous", alias="X-User-ID"),
    session: AsyncSession = Depends(get_session),
):
    """
    创建版本快照

    - **knowledge_base_id**: 知识库 ID
    - **description**: 版本描述
    """
    try:
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.version_manager import get_version_manager

        # 初始化版本管理器
        neo4j = get_neo4j_client()
        version_mgr = get_version_manager(neo4j)

        # 创建版本
        version = await version_mgr.create_version(
            knowledge_base_id=request.knowledge_base_id,
            created_by=x_user_id,
            tenant_id=x_tenant_id,
            description=request.description,
        )

        # 保存到数据库
        repo = VersionRepository(session)
        await repo.create(version)

        return VersionResponse(
            id=version.id,
            knowledge_base_id=version.knowledge_base_id,
            version=version.version,
            snapshot=VersionSnapshotResponse(**version.snapshot.to_dict()),
            description=version.description,
            created_by=version.created_by,
            tenant_id=version.tenant_id,
            created_at=version.created_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to create version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create version: {str(e)}",
        ) from e


@router.get("/", response_model=ListVersionsResponse)
async def list_versions(
    knowledge_base_id: str,
    offset: int = 0,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    """
    列出知识库的版本历史

    - **knowledge_base_id**: 知识库 ID
    - **offset**: 偏移量
    - **limit**: 数量限制
    """
    try:
        # 从数据库获取版本列表
        repo = VersionRepository(session)
        versions, total = await repo.list_by_knowledge_base(
            knowledge_base_id=knowledge_base_id, offset=offset, limit=limit
        )

        return ListVersionsResponse(
            versions=[
                VersionResponse(
                    id=v.id,
                    knowledge_base_id=v.knowledge_base_id,
                    version=v.version,
                    snapshot=VersionSnapshotResponse(**v.snapshot.to_dict()),
                    description=v.description,
                    created_by=v.created_by,
                    tenant_id=v.tenant_id,
                    created_at=v.created_at.isoformat(),
                )
                for v in versions
            ],
            total=total,
        )

    except Exception as e:
        logger.error(f"Failed to list versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list versions: {str(e)}",
        ) from e


@router.get("/{version_id}", response_model=VersionResponse)
async def get_version(version_id: str, session: AsyncSession = Depends(get_session)):
    """
    获取版本详情

    - **version_id**: 版本 ID
    """
    try:
        # 从数据库获取版本
        repo = VersionRepository(session)
        version = await repo.get_by_id(version_id)

        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

        return VersionResponse(
            id=version.id,
            knowledge_base_id=version.knowledge_base_id,
            version=version.version,
            snapshot=VersionSnapshotResponse(**version.snapshot.to_dict()),
            description=version.description,
            created_by=version.created_by,
            tenant_id=version.tenant_id,
            created_at=version.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get version: {str(e)}",
        ) from e


@router.post("/rollback")
async def rollback_version(
    request: RollbackRequest, x_user_id: str = Header("anonymous", alias="X-User-ID")
):
    """
    回滚到指定版本

    - **version_id**: 目标版本 ID
    """
    try:
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.version_manager import get_version_manager

        # 初始化版本管理器
        neo4j = get_neo4j_client()
        version_mgr = get_version_manager(neo4j)

        # 执行回滚
        success = await version_mgr.rollback_to_version(
            version_id=request.version_id, initiated_by=x_user_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rollback failed"
            )

        return {"message": "Rollback completed successfully", "version_id": request.version_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback: {str(e)}",
        ) from e


@router.delete("/{version_id}")
async def delete_version(version_id: str, session: AsyncSession = Depends(get_session)):
    """
    删除版本

    - **version_id**: 版本 ID
    """
    try:
        # 从数据库删除版本
        repo = VersionRepository(session)
        success = await repo.delete(version_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

        return {"message": "Version deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete version: {str(e)}",
        ) from e
