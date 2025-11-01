"""
Query Enhancement API endpoints - P2级功能

包含：
- Query Expansion（查询扩展）
- Multi-Query Generation（多查询生成）
- HyDE（假设文档嵌入）
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.retrieval import (
    HyDERequest,
    HyDEResponse,
    MultiQueryRequest,
    MultiQueryResponse,
    QueryExpansionRequest,
    QueryExpansionResponse,
)
from app.services.query.expansion_service import QueryExpansionService
from app.services.query.hyde_service import HyDEService
from app.services.query.multi_query_service import MultiQueryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/query", tags=["Query Enhancement"])

# 初始化服务（懒加载）
_expansion_service = None
_multi_query_service = None
_hyde_service = None


def get_expansion_service() -> QueryExpansionService:
    """获取查询扩展服务实例"""
    global _expansion_service
    if _expansion_service is None:
        logger.info("Initializing QueryExpansionService...")
        _expansion_service = QueryExpansionService(
            methods=["synonym", "spelling"],
            max_expansions=5,
            llm_endpoint=getattr(settings, "LLM_ENDPOINT", None),
        )
    return _expansion_service


def get_multi_query_service() -> MultiQueryService:
    """获取多查询生成服务实例"""
    global _multi_query_service
    if _multi_query_service is None:
        logger.info("Initializing MultiQueryService...")
        _multi_query_service = MultiQueryService(
            llm_endpoint=getattr(settings, "LLM_ENDPOINT", None),
            num_queries=3,
        )
    return _multi_query_service


def get_hyde_service() -> HyDEService:
    """获取HyDE服务实例"""
    global _hyde_service
    if _hyde_service is None:
        logger.info("Initializing HyDEService...")
        _hyde_service = HyDEService(
            llm_endpoint=getattr(settings, "LLM_ENDPOINT", None),
        )
    return _hyde_service


@router.post("/expand", response_model=QueryExpansionResponse)
async def expand_query(request: QueryExpansionRequest) -> QueryExpansionResponse:
    """
    查询扩展 - Query Expansion

    功能：
    - 同义词扩展（基于词典，快速低成本）
    - 拼写纠错（中文拼音、英文拼写）
    - 可选LLM改写（高级模式，enable_llm=true）

    优势：
    - 默认策略不依赖LLM，延迟低（<50ms）
    - 成本可控（词典查询免费）
    - 召回率提升15-25%

    参数：
    - **query**: 原始查询文本
    - **enable_llm**: 是否启用LLM扩展（可选，成本高）
    - **max_expansions**: 最大扩展数量（默认3）
    - **methods**: 扩展方法列表 ['synonym', 'spelling', 'llm']

    返回：
    - **original**: 原始查询
    - **expanded**: 扩展后的查询列表（包含原查询）
    - **weights**: 每个查询的权重
    - **method**: 使用的扩展方法
    - **latency_ms**: 扩展延迟（毫秒）
    """
    try:
        service = get_expansion_service()

        # 如果用户指定了methods，临时更新服务配置
        if request.methods:
            service.methods = request.methods

        result = await service.expand(
            query=request.query,
            enable_llm=request.enable_llm,
        )

        response = QueryExpansionResponse(
            original=result.original,
            expanded=result.expanded[: request.max_expansions],
            weights=result.weights[: request.max_expansions],
            method=result.method,
            latency_ms=result.latency_ms,
        )

        logger.info(
            f"Query expansion: '{request.query}' -> {len(response.expanded)} queries "
            f"in {response.latency_ms:.1f}ms"
        )

        return response

    except Exception as e:
        logger.error(f"Query expansion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query expansion failed: {str(e)}") from e


@router.post("/multi-query", response_model=MultiQueryResponse)
async def generate_multi_query(request: MultiQueryRequest) -> MultiQueryResponse:
    """
    多查询生成 - Multi-Query Generation

    功能：
    - 从单个查询生成多个变体查询
    - 使用LLM生成语义相似但表达不同的查询
    - 提高复杂查询的召回率和准确性

    优势：
    - 覆盖不同的查询角度
    - 提升复杂问题的准确率（目标≥20%）
    - 适合开放式问题和多意图查询

    参数：
    - **query**: 原始查询文本
    - **num_queries**: 生成的查询数量（不包含原查询，默认3）

    返回：
    - **original**: 原始查询
    - **queries**: 生成的查询列表（包含原查询）
    - **method**: 生成方法（llm/template/hybrid）
    - **latency_ms**: 生成延迟（毫秒）
    """
    try:
        service = get_multi_query_service()

        result = await service.generate(
            query=request.query,
            num_queries=request.num_queries,
        )

        response = MultiQueryResponse(
            original=result.original,
            queries=result.queries,
            method=result.method,
            latency_ms=result.latency_ms,
        )

        logger.info(
            f"Multi-query generation: '{request.query}' -> {len(response.queries)} queries "
            f"in {response.latency_ms:.1f}ms (method={response.method})"
        )

        return response

    except Exception as e:
        logger.error(f"Multi-query generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Multi-query generation failed: {str(e)}") from e


@router.post("/hyde", response_model=HyDEResponse)
async def generate_hyde(request: HyDERequest) -> HyDEResponse:
    """
    HyDE - Hypothetical Document Embeddings

    核心思想：
    - 用户查询可能不完整或不精确
    - 生成一个"假设性答案"（hypothetical document）
    - 使用答案的embedding进行检索（而不是查询的embedding）
    - 假设性答案通常包含更多上下文，检索效果更好

    优势：
    - 知识密集型查询准确率提升≥25%
    - 适合开放式问题
    - 减少query-document语义差距

    适用场景：
    - "什么是量子计算？"
    - "如何实现分布式锁？"
    - "解释一下XXX原理"

    参数：
    - **query**: 原始查询文本

    返回：
    - **original_query**: 原始查询
    - **hypothetical_document**: 生成的假设性文档
    - **method**: 生成方法（llm/template）
    - **latency_ms**: 生成延迟（毫秒）
    - **token_count**: 使用的token数
    """
    try:
        service = get_hyde_service()

        result = await service.generate(query=request.query)

        response = HyDEResponse(
            original_query=result.original_query,
            hypothetical_document=result.hypothetical_document,
            method=result.method,
            latency_ms=result.latency_ms,
            token_count=result.token_count,
        )

        logger.info(
            f"HyDE generation: '{request.query}' -> {len(response.hypothetical_document)} chars "
            f"in {response.latency_ms:.1f}ms (method={response.method})"
        )

        return response

    except Exception as e:
        logger.error(f"HyDE generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"HyDE generation failed: {str(e)}") from e


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """
    获取查询增强服务的统计信息

    返回：
    - expansion_stats: 查询扩展服务统计
    - multi_query_stats: 多查询生成服务统计
    - hyde_stats: HyDE服务统计
    """
    stats = {}

    if _expansion_service:
        stats["expansion"] = _expansion_service.get_stats()

    if _multi_query_service:
        stats["multi_query"] = _multi_query_service.get_stats()

    if _hyde_service:
        stats["hyde"] = _hyde_service.get_stats()

    return {
        "services_initialized": {
            "expansion": _expansion_service is not None,
            "multi_query": _multi_query_service is not None,
            "hyde": _hyde_service is not None,
        },
        "stats": stats,
    }
