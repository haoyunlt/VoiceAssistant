"""
Health check endpoints
"""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/ready")
async def readiness_check():
    """就绪检查"""
    # TODO: 检查 Milvus、Elasticsearch 连接
    return {
        "status": "ready",
        "service": settings.APP_NAME,
    }
