"""
Multimodal Engine - 主程序入口

多模态引擎服务：提供 OCR（光学字符识别）和视觉理解功能
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.error_handler import error_handler_middleware
from app.middleware.request_context import request_context_middleware
from app.routers import health, ocr, vision, analysis
from app.services.ocr_service import OCRService
from app.services.vision_service import VisionService

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 全局服务实例
ocr_service: OCRService = None
vision_service: VisionService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时：
    - 初始化 OCR 服务
    - 初始化 Vision 服务
    - 预热模型
    
    关闭时：
    - 清理资源
    """
    global ocr_service, vision_service
    
    logger.info("=" * 60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 60)
    
    try:
        # 初始化 OCR 服务
        logger.info("Initializing OCR service...")
        ocr_service = OCRService()
        logger.info(f"✓ OCR service initialized (provider: {settings.OCR_PROVIDER})")
        
        # 初始化 Vision 服务
        logger.info("Initializing Vision service...")
        vision_service = VisionService()
        logger.info(f"✓ Vision service initialized (provider: {settings.VISION_PROVIDER})")
        
        # 设置路由中的服务实例
        health.set_services(ocr_service, vision_service)
        ocr.ocr_service = ocr_service
        vision.vision_service = vision_service
        analysis.ocr_service = ocr_service
        analysis.vision_service = vision_service
        
        logger.info("=" * 60)
        logger.info("✓ All services initialized successfully")
        logger.info(f"✓ Server ready at http://{settings.HOST}:{settings.PORT}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize services: {e}", exc_info=True)
        raise
    
    # 服务运行中...
    yield
    
    # 服务关闭
    logger.info("Shutting down services...")
    logger.info("✓ Services shutdown complete")


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="多模态引擎服务 - 提供 OCR（光学字符识别）和视觉理解功能",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 自定义中间件
    app.middleware("http")(request_context_middleware)
    app.middleware("http")(error_handler_middleware)
    
    # 注册路由
    app.include_router(health.router)
    app.include_router(ocr.router)
    app.include_router(vision.router)
    app.include_router(analysis.router)
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }
    
    return app


def main():
    """主函数"""
    app = create_app()
    
    # 启动服务
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()

