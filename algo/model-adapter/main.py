"""
Model Adapter - 模型适配器服务
负责统一不同AI模型提供商的API接口，提供标准化的调用方式
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.routers import chat, completion, embedding, health

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting Model Adapter Service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Service: {settings.SERVICE_NAME} v{settings.VERSION}")

    # 启动时初始化
    # 例如：预热模型连接、加载配置等

    yield

    # 关闭时清理
    logger.info("Shutting down Model Adapter Service...")


# 创建FastAPI应用
app = FastAPI(
    title="Model Adapter Service",
    description="模型适配器服务 - 统一多个AI模型提供商的API接口",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(completion.router, prefix="/api/v1/completion", tags=["Completion"])
app.include_router(embedding.router, prefix="/api/v1/embedding", tags=["Embedding"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "supported_providers": [
            "openai",
            "azure-openai",
            "anthropic",
            "zhipu",
            "qwen",
            "baidu",
        ],
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
