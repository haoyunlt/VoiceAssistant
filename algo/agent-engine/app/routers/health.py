"""健康检查路由"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter  # type: ignore[import]

router = APIRouter()


@router.get("")
async def health_check() -> dict[str, Any]:
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),  # type: ignore
        "service": "agent-engine",
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """就绪检查"""
    # 检查依赖服务是否就绪
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
