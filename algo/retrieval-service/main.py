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
    global retrieval_service

    logger.info("Starting Retrieval Service...")

    try:
        # 初始化检索服务
        from app.core.retrieval_service import RetrievalService

        retrieval_service = RetrievalService()
        await retrieval_service.initialize()

        logger.info("Retrieval Service started successfully")

        yield

    finally:
        logger.info("Shutting down Retrieval Service...")

        # 清理资源
        if retrieval_service:
            await retrieval_service.cleanup()

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


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "retrieval-service"}


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    global retrieval_service

    checks = {
        "service": retrieval_service is not None,
        "vector_store": retrieval_service.vector_store_client is not None if retrieval_service else False,
        "neo4j": retrieval_service.neo4j_client is not None if retrieval_service else False,
        "redis": retrieval_service.redis_client is not None if retrieval_service else False,
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.post("/retrieve")
async def retrieve(request: dict):
    """
    检索接口

    Args:
        query: 查询文本
        top_k: 返回结果数
        mode: 检索模式 (vector/bm25/graph/hybrid)
        tenant_id: 租户 ID
        filters: 过滤条件
        rerank: 是否重排序
    """
    global retrieval_service

    if not retrieval_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    query = request.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        results = await retrieval_service.retrieve(
            query=query,
            top_k=request.get("top_k", 10),
            mode=request.get("mode", "hybrid"),
            tenant_id=request.get("tenant_id"),
            filters=request.get("filters"),
            rerank=request.get("rerank", True),
        )

        return {
            "query": query,
            "results": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Error retrieving: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    global retrieval_service

    if not retrieval_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return await retrieval_service.get_stats()


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
