"""
Knowledge Service - Main Application

知识图谱服务主入口
"""

from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.graph.neo4j_client import get_neo4j_client
from app.routers import knowledge_graph
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 设置日志
setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Starting Knowledge Service...")

    # 初始化 Neo4j 客户端
    neo4j_client = get_neo4j_client()
    health = await neo4j_client.health_check()
    if health.get("healthy"):
        logger.info("Neo4j connected successfully")
    else:
        logger.warning(f"Neo4j connection issue: {health.get('error')}")

    yield

    # 关闭时
    logger.info("Shutting down Knowledge Service...")
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
app.include_router(knowledge_graph.router)


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
