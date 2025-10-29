"""
实体消歧 API路由
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/knowledge/disambiguation", tags=["Entity Disambiguation"]
)

# 全局服务实例（延迟初始化）
disambiguation_service = None


async def get_disambiguation_service():
    """获取或初始化实体消歧服务"""
    global disambiguation_service

    if disambiguation_service is None:
        logger.info("Initializing EntityDisambiguationService...")
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.entity_disambiguation_service import (
            EntityDisambiguationService,
        )

        neo4j_client = await get_neo4j_client()

        disambiguation_service = EntityDisambiguationService(
            neo4j_client=neo4j_client,
            embedding_service=None,  # TODO: 集成embedding service
            similarity_threshold=0.85,
            auto_merge=False,
        )
        logger.info("EntityDisambiguationService initialized")

    return disambiguation_service


class FindSimilarRequest(BaseModel):
    """查找相似实体请求"""

    entity_id: str = Field(..., description="实体ID")
    top_k: int | None = Field(10, ge=1, le=100, description="返回前K个相似实体")


class MergeEntitiesRequest(BaseModel):
    """合并实体请求"""

    source_entity_id: str = Field(..., description="源实体ID（将被删除）")
    target_entity_id: str = Field(..., description="目标实体ID（保留）")


class AutoMergeRequest(BaseModel):
    """自动合并请求"""

    entity_type: str | None = Field(None, description="实体类型过滤")
    dry_run: bool | None = Field(True, description="是否仅模拟（不实际合并）")


class DisambiguateRequest(BaseModel):
    """实体消歧请求"""

    entity_name: str = Field(..., description="实体名称")
    context: str | None = Field(None, description="上下文信息")


@router.post("/find-similar")
async def find_similar_entities(request: FindSimilarRequest):
    """
    查找相似实体

    基于向量相似度、名称相似度和类型匹配查找相似实体。

    参数:
    - **entity_id**: 目标实体ID
    - **top_k**: 返回前K个相似实体（默认10）

    返回:
    - similar_entities: 相似实体列表
      - entity_id: 实体ID
      - similarity: 相似度分数（0-1）

    应用场景:
    - 检测重复实体
    - 实体链接
    - 知识图谱清洗

    示例:
    ```json
    {
        "entity_id": "entity_123",
        "top_k": 10
    }
    ```
    """
    service = await get_disambiguation_service()

    try:
        similar_entities = await service.find_similar_entities(
            entity_id=request.entity_id, top_k=request.top_k
        )

        return {
            "entity_id": request.entity_id,
            "similar_entities": [
                {"entity_id": eid, "similarity": score}
                for eid, score in similar_entities
            ],
            "count": len(similar_entities),
        }

    except Exception as e:
        logger.error(f"Failed to find similar entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge")
async def merge_entities(request: MergeEntitiesRequest):
    """
    合并两个实体

    将源实体的所有关系转移到目标实体，然后删除源实体。

    ⚠️ **警告**: 此操作不可逆！

    参数:
    - **source_entity_id**: 源实体ID（将被删除）
    - **target_entity_id**: 目标实体ID（保留）

    返回:
    - success: 是否成功
    - source_entity: 源实体名称
    - target_entity: 目标实体名称
    - relationships_transferred: 转移的关系数

    工作流程:
    1. 获取两个实体
    2. 转移所有出边和入边到目标实体
    3. 删除源实体

    示例:
    ```json
    {
        "source_entity_id": "entity_456",
        "target_entity_id": "entity_123"
    }
    ```
    """
    service = await get_disambiguation_service()

    try:
        result = await service.merge_entities(
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to merge entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-merge")
async def auto_merge_duplicates(request: AutoMergeRequest):
    """
    自动合并重复实体

    扫描所有实体，自动检测并合并相似度超过阈值的实体。

    参数:
    - **entity_type**: 实体类型过滤（可选）
    - **dry_run**: 是否仅模拟（默认true，不实际合并）

    返回:
    - total_entities: 总实体数
    - duplicates_found: 发现的重复实体对数
    - merged_count: 合并的实体对数
    - dry_run: 是否为模拟运行
    - duplicates: 重复实体详情

    ⚠️ **警告**: 请先使用 `dry_run=true` 查看结果！

    示例:
    ```json
    {
        "entity_type": "Person",
        "dry_run": true
    }
    ```
    """
    service = await get_disambiguation_service()

    try:
        result = await service.auto_merge_duplicates(
            entity_type=request.entity_type, dry_run=request.dry_run
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to auto merge duplicates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disambiguate")
async def disambiguate_entity(request: DisambiguateRequest):
    """
    实体消歧

    当一个名称对应多个实体时，根据上下文选择正确的实体。

    参数:
    - **entity_name**: 实体名称
    - **context**: 上下文信息（可选）

    返回:
    - candidates: 候选实体列表
      - id: 实体ID
      - name: 实体名称
      - type: 实体类型
      - description: 实体描述
      - confidence: 置信度

    应用场景:
    - "Apple" → Apple Inc. 还是 苹果（水果）？
    - "Python" → 编程语言 还是 蟒蛇？

    示例:
    ```json
    {
        "entity_name": "Python",
        "context": "编程语言和数据分析"
    }
    ```
    """
    service = await get_disambiguation_service()

    try:
        candidates = await service.disambiguate_entity(
            entity_name=request.entity_name, context=request.context
        )

        return {
            "entity_name": request.entity_name,
            "candidates": candidates,
            "count": len(candidates),
            "ambiguous": len(candidates) > 1,
        }

    except Exception as e:
        logger.error(f"Failed to disambiguate entity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """
    获取消歧服务配置

    返回:
    - similarity_threshold: 相似度阈值
    - auto_merge: 是否自动合并
    """
    service = await get_disambiguation_service()

    return {
        "similarity_threshold": service.similarity_threshold,
        "auto_merge": service.auto_merge,
        "features": {
            "vector_similarity": True,
            "string_similarity": True,
            "type_matching": True,
            "context_disambiguation": False,  # TODO: 待实现
        },
    }
