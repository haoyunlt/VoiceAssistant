"""
Vector Store Adapter Service - 向量库适配服务

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
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global vector_store_manager

    logger.info("Starting Vector Store Adapter Service...")

    try:
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

        logger.info("Vector Store Adapter Service shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Vector Store Adapter Service",
    description="统一的向量数据库访问服务 - 支持 Milvus、pgvector 等",
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


# ========================================
# 健康检查
# ========================================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "vector-store-adapter",
        "version": "1.0.0",
    }


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    global vector_store_manager

    if not vector_store_manager:
        return {"ready": False, "reason": "VectorStoreManager not initialized"}

    checks = await vector_store_manager.health_check()

    return {
        "ready": all(checks.values()),
        "checks": checks,
    }


# ========================================
# 向量操作 API
# ========================================

@app.post("/collections/{collection_name}/insert")
async def insert_vectors(collection_name: str, request: dict):
    """
    插入向量（单条或批量）

    Args:
        collection_name: 集合名称
        request:
            backend: 后端类型 (milvus/pgvector)
            data: 向量数据（单条或列表）
                - chunk_id: 分块ID
                - document_id: 文档ID
                - content: 内容
                - embedding: 向量
                - tenant_id: 租户ID
                - metadata: 元数据（可选）
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    backend = request.get("backend", "milvus")
    data = request.get("data")

    if not data:
        raise HTTPException(status_code=400, detail="Data is required")

    try:
        # 确保是列表
        if isinstance(data, dict):
            data = [data]

        result = await vector_store_manager.insert_vectors(
            collection_name=collection_name,
            backend=backend,
            data=data,
        )

        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=backend,
            status="success",
        ).inc(len(data))

        return {
            "status": "success",
            "collection": collection_name,
            "backend": backend,
            "inserted": len(data),
            "result": result,
        }

    except Exception as e:
        logger.error(f"Error inserting vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="insert",
            backend=backend,
            status="error",
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/collections/{collection_name}/search")
async def search_vectors(collection_name: str, request: dict):
    """
    向量检索

    Args:
        collection_name: 集合名称
        request:
            backend: 后端类型 (milvus/pgvector)
            query_vector: 查询向量
            top_k: 返回结果数（默认10）
            tenant_id: 租户ID（可选，用于过滤）
            filters: 额外过滤条件（可选）
            search_params: 搜索参数（可选）
    """
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    backend = request.get("backend", "milvus")
    query_vector = request.get("query_vector")

    if not query_vector:
        raise HTTPException(status_code=400, detail="query_vector is required")

    try:
        results = await vector_store_manager.search_vectors(
            collection_name=collection_name,
            backend=backend,
            query_vector=query_vector,
            top_k=request.get("top_k", 10),
            tenant_id=request.get("tenant_id"),
            filters=request.get("filters"),
            search_params=request.get("search_params"),
        )

        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=backend,
            status="success",
        ).inc()

        return {
            "status": "success",
            "collection": collection_name,
            "backend": backend,
            "results": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Error searching vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="search",
            backend=backend,
            status="error",
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collections/{collection_name}/documents/{document_id}")
async def delete_by_document(collection_name: str, document_id: str, backend: str = "milvus"):
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

        return {
            "status": "success",
            "collection": collection_name,
            "backend": backend,
            "document_id": document_id,
            "result": result,
        }

    except Exception as e:
        logger.error(f"Error deleting vectors: {e}", exc_info=True)
        VECTOR_OPERATIONS.labels(
            operation="delete",
            backend=backend,
            status="error",
        ).inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections/{collection_name}/count")
async def get_collection_count(collection_name: str, backend: str = "milvus"):
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

        return {
            "status": "success",
            "collection": collection_name,
            "backend": backend,
            "count": count,
        }

    except Exception as e:
        logger.error(f"Error getting count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    global vector_store_manager

    if not vector_store_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return await vector_store_manager.get_stats()


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8003"))
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port} with {workers} workers")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level="info",
    )
