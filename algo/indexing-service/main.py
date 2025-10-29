"""
Indexing Service - 文档索引构建服务

功能：
1. 从 Kafka 接收文档事件
2. 从 MinIO 下载文档
3. 解析文档内容
4. 分块处理
5. 向量化（BGE-M3）
6. 存储到 Milvus
7. 构建 Neo4j 知识图谱
"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Prometheus 指标（包含 tenant_id, document_type 等维度）
DOCUMENTS_PROCESSED = Counter(
    "indexing_documents_processed_total",
    "Total number of documents processed",
    ["status", "tenant_id", "document_type"],
)
DOCUMENT_PROCESSING_TIME = Histogram(
    "indexing_document_processing_seconds",
    "Time spent processing documents",
    ["tenant_id", "document_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],  # SLO: p95 < 2.5s
)
CHUNKS_CREATED = Counter(
    "indexing_chunks_created_total",
    "Total number of chunks created",
    ["tenant_id", "document_type"],
)
VECTORS_STORED = Counter(
    "indexing_vectors_stored_total",
    "Total number of vectors stored in Milvus",
    ["tenant_id"],
)
EMBEDDING_LATENCY = Histogram(
    "indexing_embedding_seconds",
    "Time spent generating embeddings",
    ["model"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
MINIO_DOWNLOAD_TIME = Histogram(
    "indexing_minio_download_seconds",
    "Time spent downloading from MinIO",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)
ERROR_COUNTER = Counter(
    "indexing_errors_total",
    "Total number of errors by type",
    ["error_type", "tenant_id"],
)

from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    logger.info("Starting Indexing Service...")

    try:
        # 初始化组件
        from app.core.document_processor import DocumentProcessor
        from app.infrastructure.kafka_consumer import DocumentEventConsumer

        # 使用app.state存储状态，而非全局变量
        app.state.kafka_consumer = DocumentEventConsumer()
        app.state.document_processor = DocumentProcessor()

        # 初始化 DocumentProcessor（包括 Kafka Producer）
        await app.state.document_processor.initialize()

        # 启动 Kafka 消费者
        asyncio.create_task(app.state.kafka_consumer.start())

        logger.info("Indexing Service started successfully")

        yield

    finally:
        logger.info("Shutting down Indexing Service...")

        # 停止 Kafka 消费者
        if hasattr(app.state, "kafka_consumer") and app.state.kafka_consumer:
            await app.state.kafka_consumer.stop()

        # 清理资源
        if hasattr(app.state, "document_processor") and app.state.document_processor:
            await app.state.document_processor.cleanup()

        logger.info("Indexing Service shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Indexing Service",
    description="VoiceHelper 文档索引构建服务",
    version="2.0.0",
    lifespan=lifespan,
)

# 添加中间件（顺序很重要！）
from app.middleware.logging import StructuredLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware

# 1. 速率限制（最外层）
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
)

# 2. 请求ID生成
app.add_middleware(RequestIDMiddleware)

# 3. 结构化日志
app.add_middleware(StructuredLoggingMiddleware)

# 4. CORS 中间件 - 根据环境变量配置
allowed_origins = (
    os.getenv("CORS_ORIGINS", "").split(",")
    if os.getenv("CORS_ORIGINS")
    else ["http://localhost:3000", "http://localhost:8000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Tenant-ID"],
    max_age=3600,
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 注册路由
from app.routers import incremental

app.include_router(incremental.router)


# ========================================
# 健康检查
# ========================================

from typing import Any


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查"""
    return {
        "status": "healthy",
        "service": "indexing-service",
        "version": "2.0.0",
    }


@app.get("/readiness")
async def readiness_check(request: Request) -> dict[str, Any]:
    """就绪检查（包含依赖项检测）"""
    kafka_consumer = getattr(request.app.state, "kafka_consumer", None)
    document_processor = getattr(request.app.state, "document_processor", None)

    checks = {
        "kafka": False,
        "processor": False,
        "minio": False,
        "vector_store": False,
        "neo4j": False,
    }

    try:
        # Kafka Consumer检查
        checks["kafka"] = kafka_consumer is not None and kafka_consumer.is_running()

        # Processor检查
        checks["processor"] = document_processor is not None

        # 依赖项连接检查
        if document_processor:
            try:
                # MinIO检查
                checks["minio"] = await document_processor.minio_client.file_exists(
                    "_health_check_"
                )
            except Exception:
                checks["minio"] = False

            try:
                # Vector Store检查
                checks["vector_store"] = await document_processor.vector_store_client.health_check()
            except Exception:
                checks["vector_store"] = False

            try:
                # Neo4j检查
                checks["neo4j"] = await document_processor.neo4j_client.health_check()
            except Exception:
                checks["neo4j"] = False

    except Exception as e:
        logger.error(f"Readiness check error: {e}")

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": all_ready,
            "checks": checks,
        },
    )


# ========================================
# API 端点
# ========================================


@app.get("/")
async def root() -> dict[str, str]:
    """根路径"""
    return {
        "service": "indexing-service",
        "version": "2.0.0",
        "description": "VoiceHelper Document Indexing Service",
    }


@app.get("/stats")
async def get_stats(request: Request) -> dict[str, Any]:
    """获取统计信息"""
    document_processor = getattr(request.app.state, "document_processor", None)

    if not document_processor:
        raise HTTPException(status_code=503, detail="Processor not initialized")

    return await document_processor.get_stats()


@app.post("/trigger")
async def trigger_processing(document_id: str, request: Request) -> dict[str, str]:
    """手动触发文档处理（用于测试）"""
    document_processor = getattr(request.app.state, "document_processor", None)

    if not document_processor:
        raise HTTPException(status_code=503, detail="Processor not initialized")

    try:
        await document_processor.process_document(document_id)
        return {"status": "success", "document_id": document_id}
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# 信号处理
# ========================================


def handle_shutdown(signum, frame):
    """处理关闭信号"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# ========================================
# 主程序入口
# ========================================

if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
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
