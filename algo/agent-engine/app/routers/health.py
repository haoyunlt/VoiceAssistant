"""健康检查路由"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "agent-engine",
    }


@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    # 检查依赖服务是否就绪
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
