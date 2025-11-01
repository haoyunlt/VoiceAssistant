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
import time
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
from app.models.batch import (
    BatchSearchRequest,
    BatchSearchResponse,
    BatchSearchResult,
)
from app.models.hybrid import (
    HybridSearchRequest,
    HybridSearchResponse,
)
from app.models.update import (
    UpdateVectorRequest,
    UpdateVectorResponse,
)
from app.models.collection import (
    CollectionListResponse,
    CollectionInfo,
    CollectionSchemaResponse,
    CollectionSchemaField,
    CollectionStatsResponse,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from starlette.responses import Response

# OpenTelemetry imports
if settings.otel_enabled:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

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
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
VECTOR_OPERATION_ERRORS = Counter(
    "vector_operation_errors_total",
    "Total number of vector operation errors",
    ["operation", "backend", "error_type"],
)
BACKEND_HEALTH_STATUS = Gauge(
    "backend_health_status",
    "Backend health status (1=healthy, 0=unhealthy)",
    ["backend"],
)
BATCH_SIZE = Histogram(
    "vector_batch_size",
    "Size of batch operations",
    ["operation", "backend"],
    buckets=(1, 10, 50, 100, 500, 1000, 5000),
)
CACHE_HITS = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["operation"],
)
CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["operation"],
)
CACHE_HIT_RATE = Gauge(
    "cache_hit_rate",
    "Cache hit rate (hits / (hits + misses))",
    ["operation"],
)

# 全局变量
vector_store_manager = None
redis_client = None
tracer = None
search_cache = None


# 初始化 OpenTelemetry
def init_otel():
    """Initialize OpenTelemetry"""
    if not settings.otel_enabled:
        return

    try:
        # Create resource
        resource = Resource(attributes={
            SERVICE_NAME: settings.otel_service_name,
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_endpoint,
            insecure=True,  # Use insecure for local development
        )

        # Add span processor
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        global tracer
        tracer = trace.get_tracer(__name__)

        logger.info(f"OpenTelemetry initialized (endpoint: {settings.otel_endpoint})")
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator[None, None, None]:
    """应用生命周期管理"""
    global vector_store_manager, redis_client, search_cache

    logger.info("Starting Vector Store Adapter Service...")

    try:
        # Initialize OpenTelemetry
        init_otel()
        # 初始化 Redis（如果启用）
        if settings.rate_limit_enabled or settings.idempotency_enabled or settings.cache_enabled:
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

        # 初始化缓存
        if settings.cache_enabled and redis_client:
            from app.core.cache import VectorSearchCache

            search_cache = VectorSearchCache(
                redis_client=redis_client,
                ttl_seconds=settings.cache_ttl,
                enabled=True,
            )
            logger.info(f"Search cache initialized (TTL: {settings.cache_ttl}s)")

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

# OpenTelemetry instrumentation (auto-instrument FastAPI)
if settings.otel_enabled:
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")

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
    global vector_store_manager, tracer

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    start_time = time.time()

    # Create custom span if OTEL enabled
    if tracer:
        with tracer.start_as_current_span(
            "insert_vectors",
            attributes={
                "collection": collection_name,
                "backend": request.backend,
                "batch_size": len(request.data),
            },
        ):
            return await _insert_vectors_impl(collection_name, request, start_time)
    else:
        return await _insert_vectors_impl(collection_name, request, start_time)


async def _insert_vectors_impl(collection_name: str, request: InsertVectorsRequest, start_time: float) -> InsertResponse:
    """Implementation of insert vectors"""
    try:
        # 转换数据
        data = [item.model_dump() for item in request.data]
        batch_size = len(data)

        result = await vector_store_manager.insert_vectors(
            collection_name=collection_name,
            backend=request.backend,
            data=data,
        )

        duration = time.time() - start_time

        # Record metrics
        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=request.backend,
            status="success",
        ).inc(batch_size)

        VECTOR_OPERATION_DURATION.labels(
            operation="insert",
            backend=request.backend,
        ).observe(duration)

        BATCH_SIZE.labels(
            operation="insert",
            backend=request.backend,
        ).observe(batch_size)

        return InsertResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            inserted=batch_size,
            result=result,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error inserting vectors: {e}", exc_info=True)

        # Record error metrics
        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=request.backend,
            status="error",
        ).inc()

        VECTOR_OPERATION_ERRORS.labels(
            operation="insert",
            backend=request.backend,
            error_type=type(e).__name__,
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="insert",
            backend=request.backend,
        ).observe(duration)

        raise


@app.post("/collections/{collection_name}/search", response_model=SearchResponse)
async def search_vectors(collection_name: str, request: SearchVectorsRequest) -> SearchResponse:
    """
    向量检索

    Args:
        collection_name: 集合名称
        request: 搜索请求
    """
    global vector_store_manager, tracer

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    start_time = time.time()

    # Create custom span if OTEL enabled
    if tracer:
        with tracer.start_as_current_span(
            "search_vectors",
            attributes={
                "collection": collection_name,
                "backend": request.backend,
                "top_k": request.top_k,
                "has_tenant_filter": request.tenant_id is not None,
            },
        ):
            return await _search_vectors_impl(collection_name, request, start_time)
    else:
        return await _search_vectors_impl(collection_name, request, start_time)


async def _search_vectors_impl(collection_name: str, request: SearchVectorsRequest, start_time: float) -> SearchResponse:
    """Implementation of search vectors"""
    global search_cache

    from app.core.query_optimizer import query_optimizer

    cached_result = False

    # Optimize search parameters if not provided
    optimized_params = query_optimizer.optimize_search_params(
        backend=request.backend,
        top_k=request.top_k,
        search_params=request.search_params,
    )

    try:
        # Check cache if enabled
        if search_cache:
            cache_key = search_cache.get_cache_key(
                collection=collection_name,
                query_vector=request.query_vector,
                top_k=request.top_k,
                tenant_id=request.tenant_id,
                filters=request.filters,
                backend=request.backend,
            )

            cached_results = await search_cache.get(cache_key)
            if cached_results is not None:
                # Cache hit
                CACHE_HITS.labels(operation="search").inc()
                cached_result = True
                results = cached_results

                # Update cache hit rate
                _update_cache_hit_rate()
            else:
                # Cache miss
                CACHE_MISSES.labels(operation="search").inc()
                _update_cache_hit_rate()

                # Query backend with optimized params
                results = await vector_store_manager.search_vectors(
                    collection_name=collection_name,
                    backend=request.backend,
                    query_vector=request.query_vector,
                    top_k=request.top_k,
                    tenant_id=request.tenant_id,
                    filters=request.filters,
                    search_params=optimized_params,
                )

                # Store in cache
                await search_cache.set(cache_key, results)
        else:
            # No cache, query directly with optimized params
            results = await vector_store_manager.search_vectors(
                collection_name=collection_name,
                backend=request.backend,
                query_vector=request.query_vector,
                top_k=request.top_k,
                tenant_id=request.tenant_id,
                filters=request.filters,
                search_params=optimized_params,
            )

        duration = time.time() - start_time

        # Record metrics
        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=request.backend,
            status="success",
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="search",
            backend=request.backend,
        ).observe(duration)

        return SearchResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            results=results,
            count=len(results),
            cached=cached_result,  # Add cache status to response
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error searching vectors: {e}", exc_info=True)

        # Record error metrics
        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=request.backend,
            status="error",
        ).inc()

        VECTOR_OPERATION_ERRORS.labels(
            operation="search",
            backend=request.backend,
            error_type=type(e).__name__,
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="search",
            backend=request.backend,
        ).observe(duration)

        raise


def _update_cache_hit_rate():
    """Update cache hit rate gauge"""
    try:
        hits = CACHE_HITS._value._value
        misses = CACHE_MISSES._value._value
        total = hits + misses
        if total > 0:
            hit_rate = hits / total
            CACHE_HIT_RATE.labels(operation="search").set(hit_rate)
    except Exception as e:
        logger.error(f"Error updating cache hit rate: {e}")


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
    global vector_store_manager, search_cache

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = await vector_store_manager.delete_by_document(
            collection_name=collection_name,
            backend=backend,
            document_id=document_id,
        )

        # Invalidate cache for this document
        if search_cache:
            await search_cache.invalidate_document(collection_name, document_id, backend)

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


@app.post("/collections/{collection_name}/batch_search", response_model=BatchSearchResponse)
async def batch_search_vectors(
    collection_name: str, request: BatchSearchRequest
) -> BatchSearchResponse:
    """
    批量向量检索（并行执行多个查询）

    Args:
        collection_name: 集合名称
        request: 批量搜索请求
    """
    global vector_store_manager, search_cache, tracer

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    start_time = time.time()

    # Create custom span if OTEL enabled
    if tracer:
        with tracer.start_as_current_span(
            "batch_search_vectors",
            attributes={
                "collection": collection_name,
                "backend": request.backend,
                "query_count": len(request.queries),
            },
        ):
            return await _batch_search_vectors_impl(collection_name, request, start_time)
    else:
        return await _batch_search_vectors_impl(collection_name, request, start_time)


async def _batch_search_vectors_impl(
    collection_name: str, request: BatchSearchRequest, start_time: float
) -> BatchSearchResponse:
    """Implementation of batch search vectors"""
    import asyncio

    async def _single_search(query: BatchSearchQuery) -> BatchSearchResult:
        """Execute single search"""
        cached_result = False
        try:
            # Check cache if enabled
            if search_cache:
                cache_key = search_cache.get_cache_key(
                    collection=collection_name,
                    query_vector=query.query_vector,
                    top_k=query.top_k,
                    tenant_id=query.tenant_id,
                    filters=query.filters,
                    backend=request.backend,
                )

                cached_results = await search_cache.get(cache_key)
                if cached_results is not None:
                    CACHE_HITS.labels(operation="batch_search").inc()
                    _update_cache_hit_rate()
                    cached_result = True
                    results = cached_results
                else:
                    CACHE_MISSES.labels(operation="batch_search").inc()
                    _update_cache_hit_rate()

                    results = await vector_store_manager.search_vectors(
                        collection_name=collection_name,
                        backend=request.backend,
                        query_vector=query.query_vector,
                        top_k=query.top_k,
                        tenant_id=query.tenant_id,
                        filters=query.filters,
                        search_params=query.search_params,
                    )

                    await search_cache.set(cache_key, results)
            else:
                results = await vector_store_manager.search_vectors(
                    collection_name=collection_name,
                    backend=request.backend,
                    query_vector=query.query_vector,
                    top_k=query.top_k,
                    tenant_id=query.tenant_id,
                    filters=query.filters,
                    search_params=query.search_params,
                )

            return BatchSearchResult(
                results=results,
                count=len(results),
                cached=cached_result,
            )
        except Exception as e:
            logger.error(f"Batch search single query error: {e}")
            return BatchSearchResult(
                results=[],
                count=0,
                error=str(e),
            )

    # Execute all searches in parallel
    tasks = [_single_search(query) for query in request.queries]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    duration = time.time() - start_time

    # Calculate stats
    success_count = sum(1 for r in results if r.error is None)
    error_count = len(results) - success_count
    total_count = sum(r.count for r in results)

    # Record metrics
    VECTOR_OPERATIONS.labels(
        operation="batch_search",
        backend=request.backend,
        status="success" if error_count == 0 else "partial",
    ).inc(len(request.queries))

    VECTOR_OPERATION_DURATION.labels(
        operation="batch_search",
        backend=request.backend,
    ).observe(duration)

    BATCH_SIZE.labels(
        operation="batch_search",
        backend=request.backend,
    ).observe(len(request.queries))

    return BatchSearchResponse(
        status="success" if error_count == 0 else "partial",
        collection=collection_name,
        backend=request.backend,
        results=results,
        total_count=total_count,
        success_count=success_count,
        error_count=error_count,
    )


@app.post("/collections/{collection_name}/hybrid_search", response_model=HybridSearchResponse)
async def hybrid_search_vectors(
    collection_name: str, request: HybridSearchRequest
) -> HybridSearchResponse:
    """
    混合检索（向量 + BM25）

    Args:
        collection_name: 集合名称
        request: 混合检索请求
    """
    global vector_store_manager, search_cache, tracer

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    start_time = time.time()

    # Create custom span if OTEL enabled
    if tracer:
        with tracer.start_as_current_span(
            "hybrid_search_vectors",
            attributes={
                "collection": collection_name,
                "backend": request.backend,
                "fusion_method": request.fusion_method,
                "vector_weight": request.vector_weight,
            },
        ):
            return await _hybrid_search_vectors_impl(collection_name, request, start_time)
    else:
        return await _hybrid_search_vectors_impl(collection_name, request, start_time)


async def _hybrid_search_vectors_impl(
    collection_name: str, request: HybridSearchRequest, start_time: float
) -> HybridSearchResponse:
    """Implementation of hybrid search vectors"""
    from app.core.hybrid_search import hybrid_search_engine
    from app.core.query_optimizer import query_optimizer

    cached_result = False

    # Optimize search parameters
    optimized_params = query_optimizer.optimize_search_params(
        backend=request.backend,
        top_k=request.top_k,
        search_params=request.search_params,
    )

    try:
        # Check cache if enabled (cache key includes query_text)
        if search_cache:
            # Create hybrid cache key (include both vector and text)
            import xxhash
            text_hash = xxhash.xxh64(request.query_text.encode('utf-8')).hexdigest()
            cache_key = f"{search_cache.key_prefix}:hybrid:{request.backend}:{collection_name}:{request.top_k}:{text_hash}:" + \
                        search_cache._hash_vector(request.query_vector)

            cached_results = await search_cache.get(cache_key)
            if cached_results is not None:
                CACHE_HITS.labels(operation="hybrid_search").inc()
                _update_cache_hit_rate()
                cached_result = True
                results = cached_results
            else:
                CACHE_MISSES.labels(operation="hybrid_search").inc()
                _update_cache_hit_rate()

                # 1. Vector search
                vector_results = await vector_store_manager.search_vectors(
                    collection_name=collection_name,
                    backend=request.backend,
                    query_vector=request.query_vector,
                    top_k=request.top_k * 2,  # Get more for fusion
                    tenant_id=request.tenant_id,
                    filters=request.filters,
                    search_params=optimized_params,
                )

                # 2. BM25 search (simulate with vector results for now)
                # In production, you'd maintain a separate BM25 index
                # For now, we'll use a simple text matching on the vector results
                bm25_results = _simulate_bm25_search(vector_results, request.query_text, request.top_k * 2)

                # 3. Fusion
                if request.fusion_method == "rrf":
                    results = hybrid_search_engine.reciprocal_rank_fusion(
                        vector_results=vector_results,
                        bm25_results=bm25_results,
                        k=request.rrf_k,
                        vector_weight=request.vector_weight,
                    )
                else:  # weighted
                    results = hybrid_search_engine.weighted_fusion(
                        vector_results=vector_results,
                        bm25_results=bm25_results,
                        vector_weight=request.vector_weight,
                    )

                # Limit to top_k
                results = results[:request.top_k]

                # Store in cache
                await search_cache.set(cache_key, results)
        else:
            # No cache, perform hybrid search directly
            vector_results = await vector_store_manager.search_vectors(
                collection_name=collection_name,
                backend=request.backend,
                query_vector=request.query_vector,
                top_k=request.top_k * 2,
                tenant_id=request.tenant_id,
                filters=request.filters,
                search_params=optimized_params,
            )

            bm25_results = _simulate_bm25_search(vector_results, request.query_text, request.top_k * 2)

            if request.fusion_method == "rrf":
                results = hybrid_search_engine.reciprocal_rank_fusion(
                    vector_results=vector_results,
                    bm25_results=bm25_results,
                    k=request.rrf_k,
                    vector_weight=request.vector_weight,
                )
            else:
                results = hybrid_search_engine.weighted_fusion(
                    vector_results=vector_results,
                    bm25_results=bm25_results,
                    vector_weight=request.vector_weight,
                )

            results = results[:request.top_k]

        duration = time.time() - start_time

        # Record metrics
        VECTOR_OPERATIONS.labels(
            operation="hybrid_search",
            backend=request.backend,
            status="success",
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="hybrid_search",
            backend=request.backend,
        ).observe(duration)

        return HybridSearchResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            results=results,
            count=len(results),
            fusion_method=request.fusion_method,
            vector_weight=request.vector_weight,
            cached=cached_result,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error in hybrid search: {e}", exc_info=True)

        VECTOR_OPERATIONS.labels(
            operation="hybrid_search",
            backend=request.backend,
            status="error",
        ).inc()

        VECTOR_OPERATION_ERRORS.labels(
            operation="hybrid_search",
            backend=request.backend,
            error_type=type(e).__name__,
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="hybrid_search",
            backend=request.backend,
        ).observe(duration)

        raise


def _simulate_bm25_search(documents: list[dict], query_text: str, top_k: int) -> list[dict]:
    """
    Simulate BM25 search (for demo purposes)

    In production, you'd maintain a separate BM25 index.
    This is a simple keyword matching simulation.
    """
    query_terms = set(query_text.lower().split())

    scored_docs = []
    for doc in documents:
        content = doc.get("content", "").lower()
        # Simple term frequency score
        score = sum(1 for term in query_terms if term in content)
        if score > 0:
            scored_docs.append({**doc, "score": float(score)})

    # Sort by score and return top_k
    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    return scored_docs[:top_k]


@app.put("/collections/{collection_name}/vectors/{chunk_id}", response_model=UpdateVectorResponse)
async def update_vector(
    collection_name: str,
    chunk_id: str,
    request: UpdateVectorRequest,
) -> UpdateVectorResponse:
    """
    更新向量（支持部分更新）

    Args:
        collection_name: 集合名称
        chunk_id: 分块ID
        request: 更新请求
    """
    global vector_store_manager, search_cache, tracer

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Validate: at least one field to update
    if not any([request.vector, request.content, request.metadata]):
        raise HTTPException(
            status_code=400,
            detail="At least one of vector, content, or metadata must be provided"
        )

    start_time = time.time()

    # Create custom span if OTEL enabled
    if tracer:
        updated_fields = []
        if request.vector:
            updated_fields.append("vector")
        if request.content:
            updated_fields.append("content")
        if request.metadata:
            updated_fields.append("metadata")

        with tracer.start_as_current_span(
            "update_vector",
            attributes={
                "collection": collection_name,
                "backend": request.backend,
                "chunk_id": chunk_id,
                "updated_fields": ",".join(updated_fields),
            },
        ):
            return await _update_vector_impl(collection_name, chunk_id, request, start_time)
    else:
        return await _update_vector_impl(collection_name, chunk_id, request, start_time)


async def _update_vector_impl(
    collection_name: str,
    chunk_id: str,
    request: UpdateVectorRequest,
    start_time: float,
) -> UpdateVectorResponse:
    """Implementation of update vector"""
    try:
        # Build update data
        update_data = {"chunk_id": chunk_id}
        updated_fields = []

        if request.vector is not None:
            update_data["vector"] = request.vector
            updated_fields.append("vector")

        if request.content is not None:
            update_data["content"] = request.content
            updated_fields.append("content")

        if request.metadata is not None:
            update_data.update(request.metadata)
            updated_fields.append("metadata")

        # For now, we'll use delete + insert as update
        # In production, you'd implement native update operations
        # 1. Delete old vector
        await vector_store_manager.delete_by_chunk(
            collection_name=collection_name,
            backend=request.backend,
            chunk_id=chunk_id,
        )

        # 2. Insert updated vector
        result = await vector_store_manager.insert_vectors(
            collection_name=collection_name,
            backend=request.backend,
            data=[update_data],
        )

        # Invalidate cache for this collection
        if search_cache:
            await search_cache.invalidate_collection(collection_name, request.backend)

        duration = time.time() - start_time

        # Record metrics
        VECTOR_OPERATIONS.labels(
            operation="update",
            backend=request.backend,
            status="success",
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="update",
            backend=request.backend,
        ).observe(duration)

        return UpdateVectorResponse(
            status="success",
            collection=collection_name,
            backend=request.backend,
            chunk_id=chunk_id,
            updated_fields=updated_fields,
            result=result,
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Error updating vector: {e}", exc_info=True)

        VECTOR_OPERATIONS.labels(
            operation="update",
            backend=request.backend,
            status="error",
        ).inc()

        VECTOR_OPERATION_ERRORS.labels(
            operation="update",
            backend=request.backend,
            error_type=type(e).__name__,
        ).inc()

        VECTOR_OPERATION_DURATION.labels(
            operation="update",
            backend=request.backend,
        ).observe(duration)

        raise


@app.get("/collections", response_model=CollectionListResponse)
async def list_collections(backend: str = "milvus") -> CollectionListResponse:
    """
    列出所有集合

    Args:
        backend: 后端类型
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get backend instance
        backend_instance = vector_store_manager._get_backend(backend)

        # List collections (implementation depends on backend)
        if backend == "milvus":
            from pymilvus import utility
            collection_names = utility.list_collections()
        else:  # pgvector
            # For pgvector, we'd query information_schema
            # For now, return empty list as demo
            collection_names = []

        # Get info for each collection
        collections = []
        for name in collection_names:
            try:
                count = await backend_instance.get_count(name)
                collections.append(
                    CollectionInfo(
                        name=name,
                        backend=backend,
                        count=count,
                        dimension=None,  # Would need to query collection schema
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to get info for collection {name}: {e}")

        return CollectionListResponse(
            status="success",
            collections=collections,
            total=len(collections),
        )

    except Exception as e:
        logger.error(f"Error listing collections: {e}", exc_info=True)
        raise


@app.get("/collections/{collection_name}/schema", response_model=CollectionSchemaResponse)
async def get_collection_schema(
    collection_name: str, backend: str = "milvus"
) -> CollectionSchemaResponse:
    """
    获取集合Schema

    Args:
        collection_name: 集合名称
        backend: 后端类型
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Define standard schema (same for all collections in our system)
        fields = [
            CollectionSchemaField(
                name="chunk_id",
                type="string",
                description="分块唯一标识"
            ),
            CollectionSchemaField(
                name="document_id",
                type="string",
                description="文档ID"
            ),
            CollectionSchemaField(
                name="content",
                type="string",
                description="文本内容"
            ),
            CollectionSchemaField(
                name="embedding",
                type="float_vector",
                description="向量嵌入"
            ),
            CollectionSchemaField(
                name="tenant_id",
                type="string",
                description="租户ID"
            ),
            CollectionSchemaField(
                name="timestamp",
                type="int64",
                description="时间戳"
            ),
        ]

        return CollectionSchemaResponse(
            status="success",
            collection=collection_name,
            backend=backend,
            fields=fields,
        )

    except Exception as e:
        logger.error(f"Error getting collection schema: {e}", exc_info=True)
        raise


@app.get("/collections/{collection_name}/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    collection_name: str, backend: str = "milvus"
) -> CollectionStatsResponse:
    """
    获取集合统计信息

    Args:
        collection_name: 集合名称
        backend: 后端类型
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        backend_instance = vector_store_manager._get_backend(backend)

        # Get count
        count = await backend_instance.get_count(collection_name)

        # Build extended stats
        stats = {
            "backend": backend,
        }

        # Add backend-specific stats
        if backend == "milvus":
            from pymilvus import utility
            if utility.has_collection(collection_name):
                # Could add Milvus-specific stats here
                stats["exists"] = True
        else:
            stats["exists"] = True

        return CollectionStatsResponse(
            status="success",
            collection=collection_name,
            backend=backend,
            count=count,
            dimension=None,  # Would need to query from collection
            stats=stats,
        )

    except Exception as e:
        logger.error(f"Error getting collection stats: {e}", exc_info=True)
        raise


@app.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """获取统计信息"""
    global vector_store_manager, search_cache

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    stats = {
        "vector_store_manager": vector_store_manager.get_stats(),
    }

    # Add cache stats if enabled
    if search_cache:
        stats["cache"] = await search_cache.get_stats()

    return StatsResponse(
        status="success",
        **stats,
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
