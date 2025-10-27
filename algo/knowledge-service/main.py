"""
Knowledge Service - Main Application

知识图谱服务主入口
"""

from contextlib import asynccontextmanager

from app.core.config import settings
import logging, setup_logging
from app.graph.knowledge_graph_service import get_kg_service
from app.graph.neo4j_client import get_neo4j_client
from app.routers import knowledge_graph
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 设置日志
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# 全局服务实例
kafka_producer = None
compensation_service = None
cleanup_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global kafka_producer, compensation_service, cleanup_service

    # 启动时
    logger.info("Starting Knowledge Service...")

    # 初始化 Neo4j 客户端
    neo4j_client = get_neo4j_client()
    health = await neo4j_client.health_check()
    if health.get("healthy"):
        logger.info("Neo4j connected successfully")
    else:
        logger.warning(f"Neo4j connection issue: {health.get('error')}")

    # 初始化 Kafka 生产者
    try:
        from app.infrastructure.kafka_producer import get_kafka_producer
        kafka_producer = await get_kafka_producer()
        logger.info("Kafka producer initialized")

        # 注入到知识图谱服务
        kg_service = get_kg_service(kafka_producer=kafka_producer)
        logger.info("Knowledge graph service initialized with Kafka")
    except Exception as e:
        logger.warning(f"Failed to initialize Kafka producer: {e}")
        kafka_producer = None

    # 初始化 Redis 客户端（用于事件补偿和清理）
    try:
        import os

        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected successfully")

        # 初始化事件补偿服务
        if kafka_producer:
            from app.infrastructure.event_compensation import EventCompensationService
            compensation_service = EventCompensationService(
                redis_client=redis_client,
                kafka_producer=kafka_producer,
                max_retries=3
            )
            logger.info("Event compensation service initialized")

        # 初始化清理服务
        from app.services.cleanup_service import CleanupService
        cleanup_service = CleanupService(
            neo4j_client=neo4j_client,
            redis_client=redis_client
        )

        # 启动定期清理任务（每24小时）
        await cleanup_service.start_cleanup_task(interval_hours=24)
        logger.info("Cleanup service initialized and started")

    except Exception as e:
        logger.warning(f"Failed to initialize Redis services: {e}")

    yield

    # 关闭时
    logger.info("Shutting down Knowledge Service...")

    # 停止清理任务
    if cleanup_service:
        await cleanup_service.stop_cleanup_task()

    # 关闭 Kafka 生产者
    if kafka_producer:
        try:
            from app.infrastructure.kafka_producer import close_kafka_producer
            await close_kafka_producer()
        except Exception as e:
            logger.error(f"Failed to close Kafka producer: {e}")

    # 关闭 Neo4j 客户端
    await neo4j_client.close()


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Knowledge Graph Service - 知识图谱服务",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.routers import admin, community, disambiguation

app.include_router(knowledge_graph.router)
app.include_router(community.router)
app.include_router(disambiguation.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower(),
    )
