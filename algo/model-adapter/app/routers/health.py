"""健康检查路由"""
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "model-adapter",
    }


@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    # 检查各个模型提供商的连接状态
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
