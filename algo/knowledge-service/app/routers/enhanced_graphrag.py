"""
Enhanced GraphRAG Router - 增强版GraphRAG API路由

包含所有优化功能的API端点
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enhanced", tags=["enhanced-graphrag"])


# ============= Request/Response Models =============


class EnhancedIndexBuildRequest(BaseModel):
    """增强版索引构建请求"""

    document_id: str = Field(..., description="文档ID")
    chunks: list[dict[str, Any]] = Field(..., description="文本块列表")
    domain: str = Field(default="general", description="领域")
    use_gds: bool = Field(default=True, description="是否使用Neo4j GDS")
    enable_entity_linking: bool = Field(default=True, description="是否启用实体链接")
    enable_temporal: bool = Field(default=False, description="是否启用时序图谱")


class EnhancedIndexBuildResponse(BaseModel):
    """增强版索引构建响应"""

    success: bool
    document_id: str
    entities_count: int
    relations_count: int
    communities_count: int
    duration_seconds: float
    enhancements: dict[str, Any]


class EntityLinkingRequest(BaseModel):
    """实体链接请求"""

    document_ids: list[str] = Field(..., description="文档ID列表")
    method: str = Field(default="hybrid", description="链接方法: text/embedding/hybrid")


class EntityLinkingResponse(BaseModel):
    """实体链接响应"""

    success: bool
    documents_processed: int
    total_merged: int
    duration_seconds: float | None = None


class TemporalQueryRequest(BaseModel):
    """时序查询请求"""

    entity_text: str = Field(..., description="实体文本")
    timestamp: str = Field(..., description="查询时间点 (ISO 8601)")
    max_depth: int = Field(default=1, description="关系深度")


class TemporalQueryResponse(BaseModel):
    """时序查询响应"""

    found: bool
    entity: dict[str, Any] | None = None
    timestamp: str | None = None
    relations: list[dict[str, Any]] = []
    relations_count: int = 0


class CacheStatsResponse(BaseModel):
    """缓存统计响应"""

    hit_count: int
    miss_count: int
    total_requests: int
    hit_rate: float


class ServiceStatsResponse(BaseModel):
    """服务统计响应"""

    cache: dict[str, Any]
    fallback: dict[str, Any]
    llm_model: dict[str, Any]
    temporal: dict[str, Any] | None = None


# ============= API Endpoints =============


@router.post("/build-index", response_model=EnhancedIndexBuildResponse)
async def build_enhanced_index(request: EnhancedIndexBuildRequest, req: Request):
    """
    构建增强版GraphRAG索引

    包含以下优化：
    - LLM调用缓存
    - Token计量与成本追踪
    - 错误处理与降级
    - Neo4j GDS社区检测
    - 实体链接去重
    - 时序图谱支持（可选）
    """
    try:
        from app.services.enhanced_graphrag_service import get_enhanced_graphrag_service
        from app.graph.neo4j_client import get_neo4j_client
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.services.embedding_service import get_embedding_service

        # 获取Redis客户端
        redis_client = getattr(req.app.state, "redis_client", None)
        if not redis_client:
            raise HTTPException(status_code=500, detail="Redis not available")

        # 获取服务实例
        neo4j = get_neo4j_client()
        extractor = get_llm_entity_extractor()
        embedding = get_embedding_service()

        service = get_enhanced_graphrag_service(
            neo4j_client=neo4j,
            llm_entity_extractor=extractor,
            embedding_service=embedding,
            redis_client=redis_client,
            enable_cache=True,
            enable_entity_linking=request.enable_entity_linking,
            enable_temporal=request.enable_temporal,
        )

        # 构建索引
        result = await service.build_index_with_enhancements(
            document_id=request.document_id,
            chunks=request.chunks,
            domain=request.domain,
            use_gds=request.use_gds,
        )

        return EnhancedIndexBuildResponse(**result)

    except Exception as e:
        logger.error(f"Enhanced index build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entity-linking", response_model=EntityLinkingResponse)
async def link_entities(request: EntityLinkingRequest, req: Request):
    """
    执行实体链接

    跨文档合并重复实体，提升知识图谱质量
    """
    try:
        from datetime import datetime
        from app.services.entity_linking_service import get_entity_linking_service
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.embedding_service import get_embedding_service

        start_time = datetime.now()

        neo4j = get_neo4j_client()
        embedding = get_embedding_service()
        service = get_entity_linking_service(neo4j, embedding)

        # 执行链接
        result = await service.link_entities_across_documents(
            document_ids=request.document_ids, method=request.method
        )

        duration = (datetime.now() - start_time).total_seconds()
        result["duration_seconds"] = duration

        return EntityLinkingResponse(**result)

    except Exception as e:
        logger.error(f"Entity linking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/temporal/query", response_model=TemporalQueryResponse)
async def query_temporal(request: TemporalQueryRequest):
    """
    时序图谱查询

    查询指定时间点的实体及其关系
    """
    try:
        from app.services.temporal_graph_service import get_temporal_graph_service
        from app.graph.neo4j_client import get_neo4j_client

        neo4j = get_neo4j_client()
        service = get_temporal_graph_service(neo4j)

        result = await service.query_entity_at_time(
            entity_text=request.entity_text,
            timestamp=request.timestamp,
            max_depth=request.max_depth,
        )

        return TemporalQueryResponse(**result)

    except Exception as e:
        logger.error(f"Temporal query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(req: Request):
    """
    获取LLM缓存统计信息

    返回缓存命中率等指标
    """
    try:
        from app.services.llm_cache_service import get_llm_cache_service

        redis_client = getattr(req.app.state, "redis_client", None)
        if not redis_client:
            raise HTTPException(status_code=500, detail="Redis not available")

        cache = get_llm_cache_service(redis_client)
        stats = cache.get_stats()

        return CacheStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/invalidate/{document_id}")
async def invalidate_cache(document_id: str, req: Request):
    """
    失效文档缓存

    删除指定文档相关的所有缓存
    """
    try:
        from app.services.llm_cache_service import get_llm_cache_service

        redis_client = getattr(req.app.state, "redis_client", None)
        if not redis_client:
            raise HTTPException(status_code=500, detail="Redis not available")

        cache = get_llm_cache_service(redis_client)
        deleted = await cache.invalidate_document_cache(document_id)

        return {"success": True, "deleted_keys": deleted}

    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ServiceStatsResponse)
async def get_service_stats(req: Request, document_id: str | None = None):
    """
    获取服务统计信息

    包括缓存、降级、LLM模型等信息
    """
    try:
        from app.services.enhanced_graphrag_service import get_enhanced_graphrag_service
        from app.graph.neo4j_client import get_neo4j_client
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.services.embedding_service import get_embedding_service

        redis_client = getattr(req.app.state, "redis_client", None)
        if not redis_client:
            raise HTTPException(status_code=500, detail="Redis not available")

        neo4j = get_neo4j_client()
        extractor = get_llm_entity_extractor()
        embedding = get_embedding_service()

        service = get_enhanced_graphrag_service(
            neo4j_client=neo4j,
            llm_entity_extractor=extractor,
            embedding_service=embedding,
            redis_client=redis_client,
        )

        stats = await service.get_enhanced_statistics(document_id)

        return ServiceStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get service stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/info")
async def get_model_info():
    """
    获取当前LLM模型信息

    返回当前使用的模型及其配置
    """
    try:
        from app.common.fallback_handler import get_llm_fallback_strategy

        strategy = get_llm_fallback_strategy()
        return strategy.get_model_info()

    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/downgrade")
async def downgrade_model():
    """
    降级LLM模型

    手动降级到成本更低的模型
    """
    try:
        from app.common.fallback_handler import get_llm_fallback_strategy

        strategy = get_llm_fallback_strategy()
        new_model = strategy.downgrade()

        if new_model:
            return {"success": True, "new_model": new_model}
        else:
            return {"success": False, "message": "Already at lowest tier"}

    except Exception as e:
        logger.error(f"Failed to downgrade model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model/upgrade")
async def upgrade_model():
    """
    升级LLM模型

    手动升级到更高质量的模型
    """
    try:
        from app.common.fallback_handler import get_llm_fallback_strategy

        strategy = get_llm_fallback_strategy()
        new_model = strategy.upgrade()

        if new_model:
            return {"success": True, "new_model": new_model}
        else:
            return {"success": False, "message": "Already at highest tier"}

    except Exception as e:
        logger.error(f"Failed to upgrade model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
