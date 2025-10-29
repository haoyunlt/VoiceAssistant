"""
Retrieval Service - 检索服务

负责从多个数据源检索相关内容：
- Milvus 向量检索
- BM25 检索
- Neo4j 图谱检索
- 混合检索 (RRF)
- Cross-Encoder 重排序
- Redis 语义缓存
"""

import os
import time
from contextlib import asynccontextmanager

# 导入配置
from app.core.config import settings

# 导入中间件
from app.middleware import (
    AuthMiddleware,
    RequestIDMiddleware,
)

# 导入可观测性
from app.observability.logging import logger, setup_logging
from app.observability.metrics import metrics
from app.observability.tracing import setup_tracing
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

# 设置结构化日志
setup_logging(
    level=settings.LOG_LEVEL,
    json_logs=not settings.DEBUG,
    service_name=settings.APP_NAME,
)

# 设置分布式追踪
setup_tracing(
    service_name=settings.OTEL_SERVICE_NAME,
    service_version=settings.APP_VERSION,
    endpoint=settings.OTEL_ENDPOINT if settings.OTEL_ENABLED else None,
    enabled=settings.OTEL_ENABLED,
)

# 全局变量
retrieval_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore
    """应用生命周期管理"""
    logger.info("Starting Retrieval Service...")

    try:
        # 初始化检索服务 - 在路由中引用
        from app.routers.retrieval import retrieval_service

        # 启动Neo4j连接
        await retrieval_service.startup()

        logger.info("Retrieval Service started successfully")

        yield

    finally:
        logger.info("Shutting down Retrieval Service...")

        # 清理资源
        from app.routers.retrieval import retrieval_service

        await retrieval_service.shutdown()

        logger.info("Retrieval Service shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Retrieval Service",
    description="GraphRAG 检索服务 - 向量检索、BM25、图谱检索、混合检索、重排序",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# 添加请求ID中间件（最外层）
app.add_middleware(RequestIDMiddleware)

# CORS 中间件 - 使用环境变量配置
allowed_origins = (
    os.getenv("CORS_ORIGINS", "").split(",")
    if os.getenv("CORS_ORIGINS")
    else [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Tenant-ID"],
    max_age=3600,
)

# 认证中间件（可选，需要配置API keys）
# 如果环境变量中配置了API_KEYS，则启用认证
api_keys_str = os.getenv("API_KEYS", "")
if api_keys_str:
    api_keys = set(api_keys_str.split(","))
    app.add_middleware(AuthMiddleware, api_keys=api_keys)
    logger.info(f"Authentication enabled with {len(api_keys)} API keys")

# 速率限制和幂等性中间件（需要Redis）
# 这些将在路由中根据需要启用

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 注册路由
from app.routers import query_enhancement, retrieval

app.include_router(retrieval.router)
app.include_router(query_enhancement.router)  # P2级：查询增强功能


# 请求日志和指标中间件
@app.middleware("http")
async def logging_and_metrics_middleware(request: Request, call_next):  # type: ignore
    """记录请求日志和指标"""
    start_time = time.time()

    # 获取请求ID
    request_id = getattr(request.state, "request_id", "unknown")

    # 记录请求开始
    logger.bind(request_id=request_id).info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        },
    )

    # 处理请求
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # 记录请求完成
        logger.bind(request_id=request_id).info(
            f"Request completed: {request.method} {request.url.path} "
            f"[{response.status_code}] in {duration:.3f}s",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration,
            },
        )

        # 记录指标
        metrics.record_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration,
        )

        return response

    except Exception as e:
        duration = time.time() - start_time

        # 记录错误
        logger.bind(request_id=request_id).error(
            f"Request failed: {request.method} {request.url.path} in {duration:.3f}s: {e}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration": duration,
                "error": str(e),
            },
        )

        # 记录错误指标
        metrics.record_error(
            error_type=type(e).__name__,
            component="http_middleware",
        )

        raise


@app.get("/health")
async def health_check() -> dict:
    """健康检查"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/ready")
async def readiness_check() -> dict:
    """就绪检查"""
    from app.routers.retrieval import retrieval_service

    checks = {
        "service": retrieval_service is not None,
        "vector_service": retrieval_service.vector_service is not None
        if retrieval_service
        else False,
        "neo4j": retrieval_service.neo4j_client is not None if retrieval_service else False,
        "graph_enabled": retrieval_service.graph_service is not None
        if retrieval_service
        else False,
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.get("/stats/neo4j")
async def get_neo4j_stats() -> dict:
    """获取Neo4j图谱统计信息"""
    from app.routers.retrieval import retrieval_service

    if not retrieval_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not retrieval_service.neo4j_client:
        return {"graph_enabled": False, "message": "Graph retrieval is not enabled"}

    try:
        stats = await retrieval_service.neo4j_client.get_statistics()
        return {"graph_enabled": True, "neo4j": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event() -> None:
    """应用启动事件"""
    # 设置服务信息指标
    metrics.set_service_info(
        {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": "development" if settings.DEBUG else "production",
        }
    )
    logger.info(
        f"{settings.APP_NAME} v{settings.APP_VERSION} started",
        extra={
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug": settings.DEBUG,
        },
    )


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = settings.HOST
    port = settings.PORT
    workers = int(os.getenv("WORKERS", "1"))
    reload = settings.DEBUG

    logger.info(
        f"Starting server on {host}:{port} with {workers} workers",
        extra={"host": host, "port": port, "workers": workers, "reload": reload},
    )

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_config=None,  # 使用我们自己的日志配置
    )
