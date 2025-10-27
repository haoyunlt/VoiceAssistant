"""
Knowledge Graph Router - 知识图谱 API 路由
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import logging
from app.graph.knowledge_graph_service import get_kg_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/kg", tags=["Knowledge Graph"])


class ExtractRequest(BaseModel):
    """提取请求"""

    text: str = Field(..., description="输入文本", min_length=1)
    source: Optional[str] = Field(None, description="数据来源")


class QueryEntityRequest(BaseModel):
    """查询实体请求"""

    entity: str = Field(..., description="实体文本")


class QueryPathRequest(BaseModel):
    """查询路径请求"""

    start_entity: str = Field(..., description="起始实体")
    end_entity: str = Field(..., description="目标实体")
    max_depth: int = Field(3, description="最大路径深度", ge=1, le=5)


class GetNeighborsRequest(BaseModel):
    """获取邻居请求"""

    entity: str = Field(..., description="实体文本")
    max_neighbors: int = Field(10, description="最大邻居数量", ge=1, le=100)


@router.post("/extract", summary="提取实体和关系并存储到图谱")
async def extract_and_store(request: ExtractRequest):
    """
    从文本提取实体和关系，并存储到知识图谱

    Args:
        - **text**: 输入文本
        - **source**: 数据来源（可选）

    Returns:
        提取和存储结果
    """
    try:
        kg_service = get_kg_service()
        result = await kg_service.extract_and_store(
            text=request.text, source=request.source
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=result.get("error", "Extraction failed")
            )

        return result

    except Exception as e:
        logger.error(f"Extract and store failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/entity", summary="查询实体")
async def query_entity(request: QueryEntityRequest):
    """
    查询实体信息（包含关系）

    Args:
        - **entity**: 实体文本

    Returns:
        实体信息
    """
    try:
        kg_service = get_kg_service()
        result = await kg_service.query_entity(entity_text=request.entity)

        if result is None:
            raise HTTPException(status_code=404, detail="Entity not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query entity failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/path", summary="查询实体路径")
async def query_path(request: QueryPathRequest):
    """
    查询两个实体之间的路径

    Args:
        - **start_entity**: 起始实体
        - **end_entity**: 目标实体
        - **max_depth**: 最大路径深度（1-5）

    Returns:
        路径列表
    """
    try:
        kg_service = get_kg_service()
        paths = await kg_service.query_path(
            start_entity=request.start_entity,
            end_entity=request.end_entity,
            max_depth=request.max_depth,
        )

        return {"paths": paths, "count": len(paths)}

    except Exception as e:
        logger.error(f"Query path failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/neighbors", summary="获取实体邻居")
async def get_neighbors(request: GetNeighborsRequest):
    """
    获取实体的邻居节点

    Args:
        - **entity**: 实体文本
        - **max_neighbors**: 最大邻居数量（1-100）

    Returns:
        邻居列表
    """
    try:
        kg_service = get_kg_service()
        neighbors = await kg_service.get_neighbors(
            entity_text=request.entity, max_neighbors=request.max_neighbors
        )

        return {"neighbors": neighbors, "count": len(neighbors)}

    except Exception as e:
        logger.error(f"Get neighbors failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", summary="获取图谱统计信息")
async def get_statistics():
    """
    获取知识图谱统计信息

    Returns:
        统计信息（节点数、关系数、标签统计等）
    """
    try:
        kg_service = get_kg_service()
        stats = await kg_service.get_statistics()
        return stats

    except Exception as e:
        logger.error(f"Get statistics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", summary="知识图谱健康检查")
async def health_check():
    """
    检查知识图谱服务健康状态

    Returns:
        健康状态
    """
    try:
        kg_service = get_kg_service()
        health = await kg_service.health_check()
        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

