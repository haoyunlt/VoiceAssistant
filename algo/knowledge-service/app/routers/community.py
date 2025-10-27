"""
社区检测 API路由
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/community", tags=["Community Detection"])

# 全局服务实例（延迟初始化）
community_service = None


async def get_community_service():
    """获取或初始化社区检测服务"""
    global community_service

    if community_service is None:
        logger.info("Initializing CommunityDetectionService...")
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.community_detection_service import CommunityDetectionService

        neo4j_client = get_neo4j_client()
        community_service = CommunityDetectionService(neo4j_client)
        logger.info("CommunityDetectionService initialized")

    return community_service


class DetectCommunitiesRequest(BaseModel):
    """社区检测请求"""

    algorithm: Literal["leiden", "louvain"] = Field(
        "leiden", description="算法类型"
    )
    max_iterations: int = Field(10, ge=1, le=100, description="最大迭代次数")
    resolution: Optional[float] = Field(
        1.0, ge=0.1, le=5.0, description="分辨率参数（仅Leiden）"
    )
    tolerance: Optional[float] = Field(
        0.0001, description="收敛容差（仅Louvain）"
    )


class GraphProjectionRequest(BaseModel):
    """图投影请求"""

    projection_name: str = Field("myGraph", description="投影名称")
    node_label: str = Field("Entity", description="节点标签")
    relationship_type: str = Field("RELATES", description="关系类型")


@router.post("/detect")
async def detect_communities(request: DetectCommunitiesRequest):
    """
    社区检测

    支持两种算法:
    - **leiden**: Leiden算法（推荐，更好的连通性保证）
    - **louvain**: Louvain算法（经典模块度优化）

    示例:
    ```json
    {
        "algorithm": "leiden",
        "max_iterations": 10,
        "resolution": 1.0
    }
    ```

    返回:
    - communities: 社区列表
    - total_communities: 社区总数
    - parameters: 算法参数
    """
    service = await get_community_service()

    try:
        if request.algorithm == "leiden":
            result = await service.detect_communities_leiden(
                max_iterations=request.max_iterations,
                resolution=request.resolution or 1.0,
            )
        else:  # louvain
            result = await service.detect_communities_louvain(
                max_iterations=request.max_iterations,
                tolerance=request.tolerance or 0.0001,
            )

        return result

    except Exception as e:
        logger.error(f"Community detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/{community_id}")
async def get_community_summary(community_id: int):
    """
    获取社区摘要

    生成指定社区的自然语言描述。

    参数:
    - **community_id**: 社区ID

    返回:
    - summary: 社区摘要
    - entity_count: 实体数量
    - relation_count: 关系数量
    """
    service = await get_community_service()

    try:
        result = await service.generate_community_summary(community_id)
        return result

    except Exception as e:
        logger.error(f"Failed to get community summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projection/create")
async def create_graph_projection(request: GraphProjectionRequest):
    """
    创建图投影

    社区检测算法需要先创建图投影。

    示例:
    ```json
    {
        "projection_name": "myGraph",
        "node_label": "Entity",
        "relationship_type": "RELATES"
    }
    ```

    返回:
    - status: 创建状态
    - node_count: 节点数量
    - relationship_count: 关系数量
    """
    service = await get_community_service()

    try:
        result = await service.create_graph_projection(
            projection_name=request.projection_name,
            node_label=request.node_label,
            relationship_type=request.relationship_type,
        )
        return result

    except Exception as e:
        logger.error(f"Failed to create graph projection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projection/{projection_name}")
async def drop_graph_projection(projection_name: str):
    """
    删除图投影

    参数:
    - **projection_name**: 投影名称

    返回:
    - status: 删除状态
    """
    service = await get_community_service()

    try:
        result = await service.drop_graph_projection(projection_name)
        return result

    except Exception as e:
        logger.error(f"Failed to drop graph projection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
