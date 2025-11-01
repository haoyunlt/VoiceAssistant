"""
GraphRAG Router - GraphRAG分层索引和全局检索API
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/graphrag", tags=["graphrag"])


# ==================== Request/Response Models ====================


class BuildIndexRequest(BaseModel):
    """构建分层索引请求"""

    document_id: str = Field(..., description="文档ID")
    chunks: list[dict[str, Any]] = Field(..., description="文本块列表")
    domain: str = Field(default="general", description="领域")


class BuildIndexResponse(BaseModel):
    """构建分层索引响应"""

    success: bool
    document_id: str
    entities_count: int
    relations_count: int
    communities_count: int
    global_summary: str
    elapsed_seconds: float


class GlobalQueryRequest(BaseModel):
    """全局查询请求"""

    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=5, description="返回结果数")


class GlobalQueryResponse(BaseModel):
    """全局查询响应"""

    query: str
    relevant_communities: list[dict[str, Any]]
    total_communities: int


class HybridRetrievalRequest(BaseModel):
    """混合检索请求"""

    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数")
    tenant_id: str | None = Field(default=None, description="租户ID")
    knowledge_base_id: str | None = Field(default=None, description="知识库ID")
    mode: str = Field(
        default="hybrid",
        description="检索模式: vector/graph/bm25/hybrid",
    )
    enable_rerank: bool = Field(default=True, description="是否启用重排")


class HybridRetrievalResponse(BaseModel):
    """混合检索响应"""

    query: str
    results: list[dict[str, Any]]
    total: int
    mode: str


class IncrementalUpdateRequest(BaseModel):
    """增量更新请求"""

    document_id: str = Field(..., description="文档ID")
    change_type: str = Field(..., description="变更类型: create/update/delete")
    content: str | None = Field(default=None, description="文档内容")
    domain: str = Field(default="general", description="领域")


class IncrementalUpdateResponse(BaseModel):
    """增量更新响应"""

    success: bool
    operation: str
    document_id: str
    details: dict[str, Any]


# ==================== API Endpoints ====================


@router.post("/build-index", response_model=BuildIndexResponse)
async def build_hierarchical_index(request: BuildIndexRequest):
    """
    构建GraphRAG分层索引

    - Level 0: 原始文本块
    - Level 1: 实体+关系
    - Level 2: 社区检测
    - Level 3: 社区摘要
    - Level 4: 全局摘要
    """
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.graphrag_service import get_graphrag_service

        # 初始化服务
        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        graphrag_service = get_graphrag_service(neo4j_client, llm_extractor)

        # 构建索引
        result = await graphrag_service.build_hierarchical_index(
            request.document_id, request.chunks, request.domain
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to build index: {result.get('error')}",
            )

        return BuildIndexResponse(
            success=True,
            document_id=result["document_id"],
            entities_count=result.get("entities_count", 0),
            relations_count=result.get("relations_count", 0),
            communities_count=result.get("communities_count", 0),
            global_summary=result.get("global_summary", ""),
            elapsed_seconds=result.get("elapsed_seconds", 0.0),
        )

    except Exception as e:
        logger.error(f"Build index failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/query/global", response_model=GlobalQueryResponse)
async def query_global(request: GlobalQueryRequest):
    """
    全局查询（基于社区摘要）

    适用于需要理解整体主题和高层次概念的查询
    """
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.graphrag_service import get_graphrag_service

        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        graphrag_service = get_graphrag_service(neo4j_client, llm_extractor)

        result = await graphrag_service.query_global(request.query, request.top_k)

        return GlobalQueryResponse(
            query=result["query"],
            relevant_communities=result["relevant_communities"],
            total_communities=result["total_communities"],
        )

    except Exception as e:
        logger.error(f"Global query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/retrieve/hybrid", response_model=HybridRetrievalResponse)
async def hybrid_retrieval(request: HybridRetrievalRequest):
    """
    混合检索（图谱 + 向量 + BM25）

    - vector: 纯向量检索
    - graph: 纯图谱检索（实体+路径）
    - bm25: 纯关键词检索
    - hybrid: 三路并行检索 + RRF融合 + 重排序
    """
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.hybrid_retrieval_service import (
            get_hybrid_retrieval_service,
        )

        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        retrieval_service = get_hybrid_retrieval_service(neo4j_client, llm_extractor)

        results = await retrieval_service.retrieve(
            query=request.query,
            top_k=request.top_k,
            tenant_id=request.tenant_id,
            knowledge_base_id=request.knowledge_base_id,
            mode=request.mode,
            enable_rerank=request.enable_rerank,
        )

        return HybridRetrievalResponse(
            query=request.query,
            results=results,
            total=len(results),
            mode=request.mode,
        )

    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/update/incremental", response_model=IncrementalUpdateResponse)
async def incremental_update(request: IncrementalUpdateRequest):
    """
    增量更新文档索引

    支持的变更类型:
    - create: 创建新文档索引
    - update: 增量更新已有文档
    - delete: 删除文档索引
    """
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.graphrag_service import get_graphrag_service
        from app.services.incremental_index_manager import (
            ChangeType,
            DocumentChange,
            get_incremental_index_manager,
        )

        # 初始化服务
        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        graphrag_service = get_graphrag_service(neo4j_client, llm_extractor)
        index_manager = get_incremental_index_manager(neo4j_client, graphrag_service)

        # 创建变更对象
        change = DocumentChange(
            document_id=request.document_id,
            change_type=ChangeType(request.change_type),
            content=request.content,
        )

        # 处理变更
        result = await index_manager.on_document_change(change, request.domain)

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Incremental update failed: {result.get('error')}",
            )

        return IncrementalUpdateResponse(
            success=True,
            operation=result.get("operation", request.change_type),
            document_id=request.document_id,
            details=result,
        )

    except Exception as e:
        logger.error(f"Incremental update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stats")
async def get_index_stats():
    """获取索引统计信息"""
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.graphrag_service import get_graphrag_service
        from app.services.incremental_index_manager import (
            get_incremental_index_manager,
        )

        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        graphrag_service = get_graphrag_service(neo4j_client, llm_extractor)
        index_manager = get_incremental_index_manager(neo4j_client, graphrag_service)

        stats = await index_manager.get_index_stats()

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Get stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/rebuild")
async def rebuild_index(
    document_ids: list[str] | None = Query(default=None),
    domain: str = Query(default="general"),
):
    """
    重建索引

    - document_ids为空: 全量重建
    - document_ids非空: 重建指定文档
    """
    try:
        from app.graph.llm_entity_extractor import get_llm_entity_extractor
        from app.graph.neo4j_client import get_neo4j_client
        from app.services.graphrag_service import get_graphrag_service
        from app.services.incremental_index_manager import (
            get_incremental_index_manager,
        )

        neo4j_client = get_neo4j_client()
        llm_extractor = get_llm_entity_extractor()
        graphrag_service = get_graphrag_service(neo4j_client, llm_extractor)
        index_manager = get_incremental_index_manager(neo4j_client, graphrag_service)

        result = await index_manager.rebuild_index(document_ids, domain)

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:
        logger.error(f"Rebuild index failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
