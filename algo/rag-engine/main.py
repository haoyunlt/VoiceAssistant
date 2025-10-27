"""
RAG Engine - 检索增强生成引擎

核心功能：
- 查询改写（Query Rewriting）
- 检索调用（Retrieval Integration）
- 上下文构建（Context Building）
- Prompt 生成（Prompt Generation）
- 答案生成（Answer Generation with LLM）
- 引用来源（Citation & Source Tracking）
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

# 添加 common 模块到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

# 导入统一基础设施模块
from cors_config import get_cors_config
from cost_tracking import cost_tracking_middleware
from exception_handlers import register_exception_handlers
from structured_logging import logging_middleware, setup_logging
from telemetry import TracingConfig, init_tracing

# 配置统一日志
setup_logging(service_name="rag-engine")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting RAG Engine...")

    try:
        # 初始化 OpenTelemetry 追踪
        tracing_config = TracingConfig(
            service_name="rag-engine",
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENV", "development"),
        )
        tracer = init_tracing(tracing_config)
        if tracer:
            logger.info("OpenTelemetry tracing initialized")

        # 初始化 RAG 服务
        from app.routers.rag import init_rag_service

        init_rag_service()

        logger.info("RAG Engine started successfully")

        yield

    finally:
        logger.info("Shutting down RAG Engine...")

        # 清理资源
        from app.routers.rag import rag_service

        if rag_service:
            await rag_service.close()

        logger.info("RAG Engine shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="RAG Engine",
    description="检索增强生成引擎 - 查询改写、上下文构建、答案生成、引用来源",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（使用统一配置）
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# 日志中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# 成本追踪中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册路由
from app.routers import rag as rag_router

app.include_router(rag_router.router, prefix="/api/v1")

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "rag-engine"}


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8006"))  # 统一使用8006端口
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port} with {workers} workers")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )
