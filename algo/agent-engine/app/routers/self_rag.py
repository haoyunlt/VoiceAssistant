"""
Self-RAG API 路由
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore[import]
from pydantic import BaseModel, Field  # type: ignore[import]

from app.api.dependencies import get_agent_engine, get_tenant_id, verify_token
from app.core.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/self-rag", tags=["self-rag"])


# 请求/响应模型
class SelfRAGQueryRequest(BaseModel):
    """Self-RAG 查询请求"""

    query: str = Field(..., description="用户查询")
    mode: str = Field(
        default="adaptive", description="Self-RAG 模式: standard/adaptive/strict/fast"
    )
    context: dict[str, Any] | None = Field(default=None, description="上下文信息")
    enable_citations: bool = Field(default=True, description="是否添加引用")
    max_refinements: int = Field(default=2, description="最大修正次数")


class SelfRAGQueryResponse(BaseModel):
    """Self-RAG 查询响应"""

    query: str
    answer: str
    confidence: float
    retrieval_strategy: str
    refinement_count: int
    hallucination_level: str | None = None
    is_grounded: bool | None = None
    citations: list[dict[str, str]] = []
    metadata: dict[str, Any] = {}


class SelfRAGStatsResponse(BaseModel):
    """Self-RAG 统计信息"""

    total_queries: int
    refinement_triggered: int
    hallucination_detected: int
    query_rewrites: int
    refinement_rate: float
    hallucination_rate: float
    cache_hit_rate: float


@router.post("/query", response_model=SelfRAGQueryResponse)
async def self_rag_query(
    request: SelfRAGQueryRequest,
    tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> SelfRAGQueryResponse:
    """
    执行 Self-RAG 查询

    Self-RAG 流程:
    1. 自适应检索（根据查询选择最优策略）
    2. 检索质量评估（相关性 + 充分性）
    3. 生成答案
    4. 幻觉检测与修正
    5. 添加引用
    """
    try:
        config = get_config()

        if not config.self_rag_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Self-RAG feature is disabled",
            )

        # 检查 agent_engine 是否有 self_rag_service 属性
        if not hasattr(agent_engine, "self_rag_service"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Self-RAG service not initialized in agent engine",
            )

        self_rag_service = agent_engine.self_rag_service

        # 导入配置类
        from app.core.self_rag.self_rag_service import SelfRAGConfig, SelfRAGMode

        # 构建配置
        rag_config = SelfRAGConfig(
            mode=SelfRAGMode(request.mode),
            max_refinement_attempts=request.max_refinements,
            hallucination_threshold=config.self_rag_hallucination_threshold,
            enable_citations=request.enable_citations,
        )

        # 执行查询
        result = await self_rag_service.query(
            query=request.query,
            context=request.context or {},
            config=rag_config,
        )

        # 构建响应
        response = SelfRAGQueryResponse(
            query=result.query,
            answer=result.answer,
            confidence=result.confidence,
            retrieval_strategy=result.retrieval_strategy,
            refinement_count=result.refinement_count,
            hallucination_level=result.hallucination_report.level.value
            if result.hallucination_report
            else None,
            is_grounded=result.hallucination_report.is_grounded
            if result.hallucination_report
            else None,
            citations=result.citations,
            metadata=result.metadata,
        )

        logger.info(
            f"Self-RAG query completed: tenant={tenant_id}, "
            f"confidence={result.confidence:.2f}, refinements={result.refinement_count}"
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid request: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Self-RAG query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Self-RAG query failed: {str(e)}",
        ) from e


@router.get("/stats", response_model=SelfRAGStatsResponse)
async def get_self_rag_stats(
    _tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> SelfRAGStatsResponse:
    """获取 Self-RAG 统计信息"""
    try:
        if not hasattr(agent_engine, "self_rag_service"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Self-RAG service not initialized",
            )

        stats = agent_engine.self_rag_service.get_stats()

        return SelfRAGStatsResponse(
            total_queries=stats["total_queries"],
            refinement_triggered=stats["refinement_triggered"],
            hallucination_detected=stats["hallucination_detected"],
            query_rewrites=stats["query_rewrites"],
            refinement_rate=stats["refinement_rate"],
            hallucination_rate=stats["hallucination_rate"],
            cache_hit_rate=stats["retriever_stats"]["cache_hit_rate"],
        )

    except Exception as e:
        logger.error(f"Failed to get Self-RAG stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
