"""
Knowledge Service - Main Application

知识图谱服务主入口
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.graph.knowledge_graph_service import get_kg_service
from app.graph.neo4j_client import get_neo4j_client
from app.routers import knowledge_graph
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# 设置日志
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting Knowledge Service...")

    # 初始化 PostgreSQL 数据库
    try:
        from app.db.database import init_database, create_tables

        init_database(
            database_url=settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO
        )
        logger.info("Database initialized successfully")

        # 创建表（如果不存在）
        await create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # 不阻塞启动，但记录错误

    # 初始化 Neo4j 客户端
    neo4j_client = get_neo4j_client()
    health = await neo4j_client.health_check()
    if health.get("healthy"):
        logger.info("Neo4j connected successfully")
    else:
        logger.warning(f"Neo4j connection issue: {health.get('error')}")

    # 初始化 Redis 客户端（用于事件补偿和清理）
    try:
        import redis.asyncio as redis

        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        )
        await redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis: {e}")
        redis_client = None

    # 初始化 Kafka 生产者（需要Redis用于补偿）
    try:
        from app.infrastructure.event_compensation import EventCompensationService
        from app.infrastructure.kafka_producer import get_kafka_producer

        # 先创建补偿服务（不传kafka_producer）
        if redis_client:
            app.state.compensation_service = EventCompensationService(
                redis_client=redis_client,
                kafka_producer=None,  # 稍后设置
                max_retries=3,
            )
            logger.info("Event compensation service initialized")

        # 创建Kafka生产者并注入补偿服务
        app.state.kafka_producer = await get_kafka_producer()
        if hasattr(app.state, "compensation_service"):
            app.state.kafka_producer.compensation_service = app.state.compensation_service
            app.state.compensation_service.kafka = app.state.kafka_producer
        logger.info("Kafka producer initialized with compensation service")

        # 注入到知识图谱服务
        get_kg_service(kafka_producer=app.state.kafka_producer)
        logger.info("Knowledge graph service initialized with Kafka")
    except Exception as e:
        logger.warning(f"Failed to initialize Kafka producer: {e}")
        app.state.kafka_producer = None

    # 初始化清理服务
    if redis_client:
        try:
            # 初始化清理服务
            from app.services.cleanup_service import CleanupService

            app.state.cleanup_service = CleanupService(
                neo4j_client=neo4j_client, redis_client=redis_client
            )

            # 启动定期清理任务
            await app.state.cleanup_service.start_cleanup_task(
                interval_hours=settings.CLEANUP_INTERVAL_HOURS
            )
            logger.info("Cleanup service initialized and started")

        except Exception as e:
            logger.warning(f"Failed to initialize cleanup service: {e}")

    # 添加中间件（需要在redis_client初始化后）
    if redis_client and settings.RATE_LIMIT_ENABLED:
        try:
            from app.middleware.idempotency import IdempotencyMiddleware
            from app.middleware.rate_limiter import RateLimiterMiddleware

            app.add_middleware(
                RateLimiterMiddleware,
                redis_client=redis_client,
                requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                burst=settings.RATE_LIMIT_BURST,
                enabled=True,
            )
            logger.info("Rate limiter middleware added")

            app.add_middleware(
                IdempotencyMiddleware,
                redis_client=redis_client,
                ttl=120,
                enabled=True,
            )
            logger.info("Idempotency middleware added")
        except Exception as e:
            logger.warning(f"Failed to add middlewares: {e}")

    yield

    # 关闭时
    logger.info("Shutting down Knowledge Service...")

    # 停止清理任务
    if hasattr(app.state, "cleanup_service") and app.state.cleanup_service:
        await app.state.cleanup_service.stop_cleanup_task()

    # 关闭 Kafka 生产者
    if hasattr(app.state, "kafka_producer") and app.state.kafka_producer:
        try:
            from app.infrastructure.kafka_producer import close_kafka_producer

            await close_kafka_producer()
        except Exception as e:
            logger.error(f"Failed to close Kafka producer: {e}")

    # 关闭数据库连接
    try:
        from app.db.database import close_database
        await close_database()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Failed to close database: {e}")

    # 关闭 Neo4j 客户端
    await neo4j_client.close()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Knowledge Graph Service - 知识图谱服务",
    lifespan=lifespan,
)

# 设置可观测性
from app.core.observability import instrument_app, setup_observability

setup_observability()
instrument_app(app)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS if settings.ENVIRONMENT == "production" else ["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# 添加限流和幂等性中间件
# 注意：需要在启动后才能使用redis_client，所以在启动事件中添加

# 注册路由
from app.routers import admin, community, disambiguation, graphrag, document, version, enhanced_graphrag

app.include_router(knowledge_graph.router)
app.include_router(community.router)
app.include_router(disambiguation.router)
app.include_router(admin.router)
app.include_router(graphrag.router)  # GraphRAG路由
app.include_router(document.router)  # 文档管理路由
app.include_router(version.router)   # 版本管理路由
app.include_router(enhanced_graphrag.router)  # 增强版GraphRAG路由（包含所有优化）


@app.get("/")
async def root() -> dict[str, Any]:
    """根路径"""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
    }


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """
    健康检查

    检查所有依赖服务的状态
    """
    health_status = {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "dependencies": {},
    }

    # 检查Neo4j
    try:
        neo4j_client = get_neo4j_client()
        neo4j_health = await neo4j_client.health_check()
        health_status["dependencies"]["neo4j"] = neo4j_health
        if not neo4j_health.get("healthy"):
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["dependencies"]["neo4j"] = {"healthy": False, "error": str(e)}
        health_status["status"] = "degraded"

    # 检查Redis（从lifespan中获取）
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client:
        try:
            await redis_client.ping()
            health_status["dependencies"]["redis"] = {"healthy": True}
        except Exception as e:
            health_status["dependencies"]["redis"] = {"healthy": False, "error": str(e)}
            health_status["status"] = "degraded"

    # 检查Kafka
    kafka_producer = getattr(request.app.state, "kafka_producer", None)
    if kafka_producer:
        try:
            metrics = kafka_producer.get_metrics()
            health_status["dependencies"]["kafka"] = {"healthy": True, "metrics": metrics}
        except Exception as e:
            health_status["dependencies"]["kafka"] = {"healthy": False, "error": str(e)}

    return health_status


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
