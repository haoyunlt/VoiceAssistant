"""
RAG Engine - 检索增强生成引擎
负责RAG流程的编排：查询理解、检索、重排序、上下文组装和生成
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.routers import health, query, rag
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting RAG Engine...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Service: {settings.SERVICE_NAME} v{settings.VERSION}")

    # 启动时初始化
    # 例如：预热模型、初始化检索器等

    yield

    # 关闭时清理
    logger.info("Shutting down RAG Engine...")


# 创建FastAPI应用
app = FastAPI(
    title="RAG Engine",
    description="检索增强生成引擎 - 负责RAG流程的完整编排",
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
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
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
