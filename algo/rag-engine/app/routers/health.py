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
        "service": "rag-engine",
    }


@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    # 检查依赖服务是否就绪（检索服务、模型适配器等）
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
