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

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局变量
retrieval_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version="1.0.0",
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

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 注册路由
from app.routers import retrieval

app.include_router(retrieval.router)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "retrieval-service"}


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    from app.routers.retrieval import retrieval_service

    checks = {
        "service": retrieval_service is not None,
        "vector_service": retrieval_service.vector_service is not None if retrieval_service else False,
        "neo4j": retrieval_service.neo4j_client is not None if retrieval_service else False,
        "graph_enabled": retrieval_service.graph_service is not None if retrieval_service else False,
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.get("/stats/neo4j")
async def get_neo4j_stats():
    """获取Neo4j图谱统计信息"""
    from app.routers.retrieval import retrieval_service

    if not retrieval_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not retrieval_service.neo4j_client:
        return {
            "graph_enabled": False,
            "message": "Graph retrieval is not enabled"
        }

    try:
        stats = await retrieval_service.neo4j_client.get_statistics()
        return {
            "graph_enabled": True,
            "neo4j": stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
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
