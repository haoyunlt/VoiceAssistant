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
    # TODO: 检查 OCR 模型加载状态
    return {
        "status": "ready",
        "service": settings.APP_NAME,
        "ocr_provider": settings.OCR_PROVIDER,
        "vision_provider": settings.VISION_PROVIDER,
    }
