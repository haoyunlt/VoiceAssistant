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
DOCUMENTS_PROCESSED = Counter(
    "indexing_documents_processed_total",
    "Total number of documents processed",
    ["status"],
)
DOCUMENT_PROCESSING_TIME = Histogram(
    "indexing_document_processing_seconds",
    "Time spent processing documents",
)
CHUNKS_CREATED = Counter(
    "indexing_chunks_created_total",
    "Total number of chunks created",
)
VECTORS_STORED = Counter(
    "indexing_vectors_stored_total",
    "Total number of vectors stored in Milvus",
)

# 全局变量
kafka_consumer = None
document_processor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global kafka_consumer, document_processor

    logger.info("Starting Indexing Service...")

    try:
        # 初始化组件
        from app.core.document_processor import DocumentProcessor
        from app.infrastructure.kafka_consumer import DocumentEventConsumer

        kafka_consumer = DocumentEventConsumer()
        document_processor = DocumentProcessor()

        # 启动 Kafka 消费者
        asyncio.create_task(kafka_consumer.start())

        logger.info("Indexing Service started successfully")

        yield

    finally:
        logger.info("Shutting down Indexing Service...")

        # 停止 Kafka 消费者
        if kafka_consumer:
            await kafka_consumer.stop()

        # 清理资源
        if document_processor:
            await document_processor.cleanup()

        logger.info("Indexing Service shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Indexing Service",
    description="VoiceHelper 文档索引构建服务",
    version="2.0.0",
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

# Prometheus metrics endpoint
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
        "service": "indexing-service",
        "version": "2.0.0",
    }


@app.get("/readiness")
async def readiness_check():
    """就绪检查"""
    global kafka_consumer, document_processor

    checks = {
        "kafka": kafka_consumer is not None and kafka_consumer.is_running(),
        "processor": document_processor is not None,
    }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


# ========================================
# API 端点
# ========================================

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "indexing-service",
        "version": "2.0.0",
        "description": "VoiceHelper Document Indexing Service",
    }


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    global document_processor

    if not document_processor:
        raise HTTPException(status_code=503, detail="Processor not initialized")

    return await document_processor.get_stats()


@app.post("/trigger")
async def trigger_processing(document_id: str):
    """手动触发文档处理（用于测试）"""
    global document_processor

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
