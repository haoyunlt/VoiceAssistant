"""
Vector Store Adapter Service - 向量库适配服务（重构版）

提供统一的向量数据库访问接口，支持：
- Milvus
- pgvector (PostgreSQL)
- 其他向量数据库（可扩展）

功能：
1. 向量插入（单条/批量）
2. 向量检索（相似度搜索）
3. 向量删除
4. 集合管理
"""

import logging
import typing
from collections.abc import Generator
from contextlib import asynccontextmanager

from app.core.settings import settings
from app.middleware import (
    IdempotencyMiddleware,
    LoggingMiddleware,
    RateLimiterMiddleware,
    error_handler_middleware,
)
from app.models import (
    CollectionCountResponse,
    DeleteResponse,
    HealthResponse,
    InsertResponse,
    InsertVectorsRequest,
    ReadyResponse,
    SearchResponse,
    SearchVectorsRequest,
    StatsResponse,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.responses import Response

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - [trace_id=%(trace_id)s]",
)
logger = logging.getLogger(__name__)

# Prometheus 指标
VECTOR_OPERATIONS = Counter(
    "vector_operations_total",
    "Total number of vector operations",
    ["operation", "backend", "status"],
)
VECTOR_OPERATION_DURATION = Histogram(
    "vector_operation_duration_seconds",
    "Vector operation duration",
    ["operation", "backend"],
)

# 全局变量
vector_store_manager = None
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator[None, None, None]:
    """应用生命周期管理"""
    global vector_store_manager, redis_client

    logger.info("Starting Vector Store Adapter Service...")

    try:
        # 初始化 Redis（如果启用）
        if settings.rate_limit_enabled or settings.idempotency_enabled:
            try:
                import redis.asyncio as aioredis

                redis_url = (
                    f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
                    if settings.redis_password
                    else f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
                )
                redis_client = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, will use memory cache")

        # 初始化向量存储管理器
        from app.core.vector_store_manager import VectorStoreManager

        vector_store_manager = VectorStoreManager()
        await vector_store_manager.initialize()

        logger.info("Vector Store Adapter Service started successfully")

        yield

    finally:
        logger.info("Shutting down Vector Store Adapter Service...")

        # 清理资源
        if vector_store_manager:
            await vector_store_manager.cleanup()

        if redis_client:
            await redis_client.close()

        logger.info("Vector Store Adapter Service shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Vector Store Adapter Service",
    description="统一的向量数据库访问服务 - 支持 Milvus、pgvector 等",
    version=settings.version,
    lifespan=lifespan,
)

# 添加中间件（顺序很重要）
# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 日志中间件（最外层，记录所有请求）
app.add_middleware(LoggingMiddleware)

# 3. 限流中间件
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimiterMiddleware,
        redis_client=redis_client,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window,
        enabled=True,
    )

# 4. 幂等性中间件
if settings.idempotency_enabled:
    app.add_middleware(
        IdempotencyMiddleware,
        redis_client=redis_client,
        ttl_seconds=settings.idempotency_ttl,
        enabled=True,
    )

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ========================================
# 健康检查
# ========================================


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.version,
    )


@app.get("/ready", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    """就绪检查"""
    global vector_store_manager

    if not vector_store_manager:
        return ReadyResponse(ready=False, reason="VectorStoreManager not initialized")

    checks = await vector_store_manager.health_check()

    return ReadyResponse(
        ready=all(checks.values()),
        checks=checks,
    )


# ========================================
# 向量操作 API
# ========================================


@app.post("/collections/{collection_name}/insert", response_model=InsertResponse)
async def insert_vectors(collection_name: str, request: InsertVectorsRequest) -> InsertResponse:
    """
    插入向量（单条或批量）

    Args:
        collection_name: 集合名称
        request: 插入请求
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # 转换数据
        data = [item.model_dump() for item in request.data]

        result = await vector_store_manager.insert_vectors(
            collection_name=collection_name,
            backend=request.backend,
            data=data,
        )

        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=request.backend,
            status="success",
        ).inc(len(data))

        return InsertResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            inserted=len(data),
            result=result,
        )

    except Exception as e:
        logger.error(f"Error inserting vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=request.backend,
            status="error",
        ).inc()
        raise


@app.post("/collections/{collection_name}/search", response_model=SearchResponse)
async def search_vectors(collection_name: str, request: SearchVectorsRequest) -> SearchResponse:
    """
    向量检索

    Args:
        collection_name: 集合名称
        request: 搜索请求
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        results = await vector_store_manager.search_vectors(
            collection_name=collection_name,
            backend=request.backend,
            query_vector=request.query_vector,
            top_k=request.top_k,
            tenant_id=request.tenant_id,
            filters=request.filters,
            search_params=request.search_params,
        )

        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=request.backend,
            status="success",
        ).inc()

        return SearchResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            results=results,
            count=len(results),
        )

    except Exception as e:
        logger.error(f"Error searching vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=request.backend,
            status="error",
        ).inc()
        raise


@app.delete(
    "/collections/{collection_name}/documents/{document_id}",
    response_model=DeleteResponse,
)
async def delete_by_document(
    collection_name: str, document_id: str, backend: str = "milvus"
) -> DeleteResponse:
    """
    删除文档的所有向量

    Args:
        collection_name: 集合名称
        document_id: 文档ID
        backend: 后端类型
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = await vector_store_manager.delete_by_document(
            collection_name=collection_name,
            backend=backend,
            document_id=document_id,
        )

        VECTOR_OPERATIONS.labels(
            operation="delete",
            backend=backend,
            status="success",
        ).inc()

        return DeleteResponse(
            status="success",
            collection=collection_name,
            backend=backend,
            document_id=document_id,
            result=result,
        )

    except Exception as e:
        logger.error(f"Error deleting vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="delete",
            backend=backend,
            status="error",
        ).inc()
        raise


@app.get("/collections/{collection_name}/count", response_model=CollectionCountResponse)
async def get_collection_count(
    collection_name: str, backend: str = "milvus"
) -> CollectionCountResponse:
    """
    获取集合中的向量数量

    Args:
        collection_name: 集合名称
        backend: 后端类型
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        count = await vector_store_manager.get_count(
            collection_name=collection_name,
            backend=backend,
        )

        return CollectionCountResponse(
            status="success",
            collection=collection_name,
            backend=backend,
            count=count,
        )

    except Exception as e:
        logger.error(f"Error getting count: {e}", exc_info=True)
        raise


@app.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """获取统计信息"""
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return StatsResponse(
        status="success",
        vector_store_manager=vector_store_manager.get_stats(),
    )


# 添加全局异常处理
@app.middleware("http")
async def error_handler(
    request: Request, call_next: typing.Callable[[Request], typing.Awaitable[Response]]
) -> JSONResponse:
    """全局错误处理中间件"""
    return await error_handler_middleware(request, call_next)


if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"Starting server on {settings.host}:{settings.port} with {settings.workers} workers"
    )

    uvicorn.run(
        "main_refactored:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
