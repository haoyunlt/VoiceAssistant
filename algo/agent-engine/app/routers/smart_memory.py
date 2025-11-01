"""
智能记忆管理 API 路由
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status  # type: ignore[import]
from pydantic import BaseModel, Field  # type: ignore[import]

from app.api.dependencies import get_agent_engine, get_tenant_id, verify_token
from app.core.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smart-memory", tags=["smart-memory"])


# 请求/响应模型
class AddMemoryRequest(BaseModel):
    """添加记忆请求"""

    content: str = Field(..., description="记忆内容")
    tier: str = Field(default="short_term", description="记忆层级: working/short_term/long_term")
    importance: float | None = Field(default=None, description="重要性（0-1），未提供则自动评估")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")


class AddMemoryResponse(BaseModel):
    """添加记忆响应"""

    memory_id: str
    tier: str
    importance: float
    message: str


class RetrieveMemoryRequest(BaseModel):
    """检索记忆请求"""

    query: str = Field(..., description="查询文本")
    top_k: int = Field(default=5, description="返回数量")
    tier_filter: str | None = Field(default=None, description="层级过滤")
    min_importance: float = Field(default=0.0, description="最小重要性")


class MemoryItem(BaseModel):
    """记忆项"""

    memory_id: str
    content: str
    tier: str
    importance: float
    current_importance: float
    access_count: int
    created_at: str
    last_accessed: str


class RetrieveMemoryResponse(BaseModel):
    """检索记忆响应"""

    memories: list[MemoryItem]
    count: int


class CompressMemoriesResponse(BaseModel):
    """压缩记忆响应"""

    summary: str
    original_count: int
    compressed_ratio: float
    message: str


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""

    total_added: int
    total_forgotten: int
    total_promoted: int
    total_demoted: int
    total_compressed: int
    memory_counts: dict[str, int]
    total_memories: int
    avg_importance: float


@router.post("/add", response_model=AddMemoryResponse)
async def add_memory(
    request: AddMemoryRequest,
    tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> AddMemoryResponse:
    """添加记忆"""
    try:
        config = get_config()

        if not config.smart_memory_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Smart memory feature is disabled",
            )

        if not hasattr(agent_engine, "smart_memory_manager"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Smart memory manager not initialized",
            )

        from app.core.memory.smart_memory_manager import MemoryTier

        # 验证层级
        try:
            tier = MemoryTier(request.tier)
        except ValueError:
            raise HTTPException(  # noqa: B904
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier: {request.tier}. Must be one of: working, short_term, long_term",
            ) from None

        manager = agent_engine.smart_memory_manager

        # 添加记忆
        memory_id = await manager.add_memory(
            content=request.content,
            tier=tier,
            importance=request.importance,
            metadata=request.metadata or {},
        )

        # 获取实际的重要性
        for tier_memories in manager.memories.values():
            for memory in tier_memories:
                if memory.memory_id == memory_id:
                    actual_importance = memory.importance
                    break

        logger.info(
            f"Added memory: tenant={tenant_id}, id={memory_id}, "
            f"tier={request.tier}, importance={actual_importance:.2f}"
        )

        return AddMemoryResponse(
            memory_id=memory_id,
            tier=request.tier,
            importance=actual_importance,
            message="Memory added successfully",
        )

    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e  # noqa: B904


@router.post("/retrieve", response_model=RetrieveMemoryResponse)
async def retrieve_memories(
    request: RetrieveMemoryRequest,
    tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> RetrieveMemoryResponse:
    """检索记忆"""
    try:
        if not hasattr(agent_engine, "smart_memory_manager"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Smart memory manager not initialized",
            )

        from app.core.memory.smart_memory_manager import MemoryTier

        # 验证层级过滤（如果提供）
        tier_filter = None
        if request.tier_filter:
            try:
                tier_filter = MemoryTier(request.tier_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid tier filter: {request.tier_filter}",
                ) from None

        manager = agent_engine.smart_memory_manager

        # 检索记忆
        memories = await manager.retrieve(
            query=request.query,
            top_k=request.top_k,
            tier_filter=tier_filter,
            min_importance=request.min_importance,
        )

        # 构建响应
        memory_items = [
            MemoryItem(
                memory_id=m.memory_id,
                content=m.content,
                tier=m.tier.value,
                importance=m.importance,
                current_importance=m.get_current_importance(),
                access_count=m.access_count,
                created_at=m.created_at.isoformat(),
                last_accessed=m.last_accessed.isoformat(),
            )
            for m in memories
        ]

        logger.info(f"Retrieved {len(memories)} memories for tenant={tenant_id}")

        return RetrieveMemoryResponse(memories=memory_items, count=len(memory_items))

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/compress", response_model=CompressMemoriesResponse)
async def compress_memories(
    tier: str = Query(default="short_term", description="要压缩的层级"),
    tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> CompressMemoriesResponse:
    """压缩指定层级的记忆"""
    try:
        config = get_config()

        if not config.memory_compression_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Memory compression is disabled",
            )

        if not hasattr(agent_engine, "smart_memory_manager"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Smart memory manager not initialized",
            )

        from app.core.memory.smart_memory_manager import MemoryTier

        try:
            memory_tier = MemoryTier(tier)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid tier: {tier}"
            ) from None

        manager = agent_engine.smart_memory_manager

        # 压缩前的记忆数
        original_count = len(manager.memories[memory_tier])

        # 执行压缩
        summary = await manager.compress_memories(tier=memory_tier)

        if not summary:
            return CompressMemoriesResponse(
                summary="",
                original_count=original_count,
                compressed_ratio=0.0,
                message=f"Not enough memories to compress in {tier}",
            )

        # 压缩后的数量（应该减少了）
        compressed_count = len(manager.memories[memory_tier])
        compressed_ratio = compressed_count / original_count if original_count > 0 else 0.0

        logger.info(
            f"Compressed memories: tenant={tenant_id}, tier={tier}, "
            f"{original_count} -> {compressed_count}"
        )

        return CompressMemoriesResponse(
            summary=summary,
            original_count=original_count,
            compressed_ratio=compressed_ratio,
            message=f"Compressed {original_count} memories to summary",
        )

    except Exception as e:
        logger.error(f"Failed to compress memories: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/maintain")
async def maintain_memories(
    tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> dict:
    """执行记忆维护（遗忘、提升、压缩）

    Returns:
        dict: 记忆维护响应
    """
    try:
        if not hasattr(agent_engine, "smart_memory_manager"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Smart memory manager not initialized",
            )

        manager = agent_engine.smart_memory_manager

        # 执行自动维护
        await manager.auto_maintain()

        stats = manager.get_stats()

        logger.info(f"Memory maintenance completed for tenant={tenant_id}")

        return {"message": "Memory maintenance completed successfully", "stats": stats}

    except Exception as e:
        logger.error(f"Failed to maintain memories: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    _tenant_id: str = Depends(get_tenant_id),
    _token_data: dict = Depends(verify_token),
    agent_engine: Any = Depends(get_agent_engine),
) -> MemoryStatsResponse:
    """获取记忆统计信息"""
    try:
        if not hasattr(agent_engine, "smart_memory_manager"):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Smart memory manager not initialized",
            )

        stats = agent_engine.smart_memory_manager.get_stats()

        return MemoryStatsResponse(
            total_added=stats["total_added"],
            total_forgotten=stats["total_forgotten"],
            total_promoted=stats["total_promoted"],
            total_demoted=stats["total_demoted"],
            total_compressed=stats["total_compressed"],
            memory_counts=stats["memory_counts"],
            total_memories=stats["total_memories"],
            avg_importance=stats["avg_importance"],
        )

    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
