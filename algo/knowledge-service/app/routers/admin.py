"""
Admin API for Knowledge Service

管理端API - 事件补偿、清理任务等
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.infrastructure.event_compensation import EventCompensationService
from app.services.cleanup_service import CleanupService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CleanupResponse(BaseModel):
    """清理响应"""

    success: bool
    results: dict[str, int]
    message: str


class CompensationResponse(BaseModel):
    """事件补偿响应"""

    success: bool
    message: str


class FailedEventsResponse(BaseModel):
    """失败事件列表响应"""

    count: int
    events: list[dict]


# 依赖注入（需要在main.py中实现）
async def get_compensation_service() -> EventCompensationService:
    """获取事件补偿服务"""
    from main import compensation_service

    return compensation_service


async def get_cleanup_service() -> CleanupService:
    """获取清理服务"""
    from main import cleanup_service

    return cleanup_service


@router.post("/cleanup/run", response_model=CleanupResponse)
async def run_cleanup(service: CleanupService = Depends(get_cleanup_service)):
    """
    手动触发清理任务

    清理内容：
    - 孤立实体（无关系的实体）
    - 孤立关系（源/目标不存在）
    - 过期缓存
    - 旧的社区检测结果
    """
    try:
        results = await service.run_cleanup()

        return CleanupResponse(
            success=True, results=results, message="Cleanup completed successfully"
        )
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/cleanup/tenant/{tenant_id}", response_model=CleanupResponse)
async def cleanup_tenant(tenant_id: str, service: CleanupService = Depends(get_cleanup_service)):
    """
    清理指定租户的所有数据

    警告：此操作不可逆！
    """
    try:
        results = await service.cleanup_tenant_data(tenant_id)

        return CleanupResponse(
            success=True,
            results=results,
            message=f"Tenant {tenant_id} data cleaned up successfully",
        )
    except Exception as e:
        logger.error(f"Tenant cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/compensation/retry", response_model=CompensationResponse)
async def retry_failed_events(
    service: EventCompensationService = Depends(get_compensation_service),
):
    """
    手动触发事件补偿（重试失败的事件）

    会重试所有记录的失败事件
    """
    try:
        await service.retry_failed_events()

        return CompensationResponse(success=True, message="Event compensation completed")
    except Exception as e:
        logger.error(f"Event compensation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/compensation/failed-events", response_model=FailedEventsResponse)
async def get_failed_events(
    start: int = 0,
    limit: int = 100,
    service: EventCompensationService = Depends(get_compensation_service),
):
    """
    获取失败事件列表

    Args:
        start: 起始位置（默认0）
        limit: 返回数量（默认100，最大1000）
    """
    try:
        # 限制最大返回数量
        limit = min(limit, 1000)
        end = start + limit - 1

        events = await service.get_failed_events(start, end)
        count = await service.get_failed_events_count()

        return FailedEventsResponse(count=count, events=events)
    except Exception as e:
        logger.error(f"Failed to get failed events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def admin_health():
    """管理端健康检查"""
    return {
        "status": "healthy",
        "services": {"event_compensation": "enabled", "cleanup": "enabled"},
    }
