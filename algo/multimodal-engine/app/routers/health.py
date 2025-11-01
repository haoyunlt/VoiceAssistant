"""
Health check endpoints
"""

from fastapi import APIRouter

from app.core.config import settings
from app.services.health_check_service import HealthCheckService
from app.services.ocr_service import OCRService
from app.services.vision_service import VisionService

router = APIRouter(tags=["Health"])

# 全局服务实例（会在main.py中初始化）
_health_service = HealthCheckService()
_ocr_service: OCRService = None
_vision_service: VisionService = None


def set_services(ocr_service: OCRService, vision_service: VisionService):
    """设置服务实例"""
    global _ocr_service, _vision_service
    _ocr_service = ocr_service
    _vision_service = vision_service


@router.get("/health")
async def health_check():
    """基础健康检查（快速检查，用于负载均衡器）"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/live")
async def liveness_check():
    """存活检查（K8s liveness probe）"""
    return await _health_service.check_liveness()


@router.get("/health/ready")
async def readiness_check():
    """
    就绪检查（K8s readiness probe）

    检查服务是否准备好接受请求：
    - OCR模型是否加载
    - Vision服务是否配置
    """
    return await _health_service.check_readiness(
        ocr_service=_ocr_service, vision_service=_vision_service
    )


@router.get("/health/detailed")
async def detailed_health_check():
    """
    详细健康检查

    包含：
    - 系统资源（CPU、内存、磁盘）
    - OCR服务状态
    - Vision服务状态
    - GPU可用性
    - 依赖库检查
    """
    return await _health_service.check_all(
        ocr_service=_ocr_service, vision_service=_vision_service, use_cache=True
    )


@router.get("/health/benchmark")
async def benchmark():
    """
    性能基准测试

    测试各模型的推理性能
    """
    return await _health_service.benchmark(ocr_service=_ocr_service, vision_service=_vision_service)


@router.get("/ready")
async def legacy_readiness_check():
    """
    就绪检查（向后兼容）

    Deprecated: 请使用 /health/ready
    """
    return {
        "status": "ready",
        "service": settings.APP_NAME,
        "ocr_provider": settings.OCR_PROVIDER,
        "vision_provider": settings.VISION_PROVIDER,
        "message": "This endpoint is deprecated. Please use /health/ready",
    }
