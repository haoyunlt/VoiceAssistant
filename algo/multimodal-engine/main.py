import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from app.core.multimodal_engine import MultimodalEngine
from app.core.ocr_engine import OCREngine
from app.core.video_engine import VideoEngine
from app.core.vision_engine import VisionEngine
from fastapi import FastAPI, File, HTTPException, UploadFile
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from prometheus_client import Counter, Histogram, make_asgi_app

# 配置日志
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    "multimodal_engine_requests_total",
    "Total number of Multimodal Engine requests",
    ["endpoint", "type"],
)
REQUEST_LATENCY = Histogram(
    "multimodal_engine_request_duration_seconds",
    "Multimodal Engine request latency in seconds",
    ["endpoint", "type"],
)

multimodal_engine: MultimodalEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global multimodal_engine

    logger.info("Starting Multimodal Engine service...")

    try:
        # 初始化各个引擎
        ocr_engine = OCREngine()
        vision_engine = VisionEngine()
        video_engine = VideoEngine()

        # 初始化 Multimodal Engine
        multimodal_engine = MultimodalEngine(
            ocr_engine=ocr_engine,
            vision_engine=vision_engine,
            video_engine=video_engine,
        )
        await multimodal_engine.initialize()

        logger.info("Multimodal Engine service started successfully.")

        # OpenTelemetry Instrumentation
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        yield

    finally:
        logger.info("Shutting down Multimodal Engine service...")
        if multimodal_engine:
            await multimodal_engine.cleanup()
        logger.info("Multimodal Engine service shut down complete.")


app = FastAPI(
    title="Multimodal Engine Service",
    version="1.0.0",
    description="Multimodal Understanding Engine for VoiceHelper",
    lifespan=lifespan,
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def read_root():
    return {"message": "Multimodal Engine Service is running!"}


@app.get("/health")
async def health_check():
    """健康检查"""
    global multimodal_engine
    if multimodal_engine and await multimodal_engine.is_ready():
        return {"status": "ok"}
    raise HTTPException(status_code=503, detail="Multimodal Engine not ready")


@app.post("/ocr")
async def ocr(
    file: UploadFile = File(...),
    language: str = "auto",
    tenant_id: str = None,
    user_id: str = None,
):
    """
    OCR 文字识别。

    Args:
        file: 图片文件
        language: 语言 (auto, en, zh, etc.)
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    global multimodal_engine
    if not multimodal_engine:
        raise HTTPException(status_code=503, detail="Multimodal Engine not initialized")

    REQUEST_COUNT.labels(endpoint="/ocr", type="ocr").inc()

    try:
        with REQUEST_LATENCY.labels(endpoint="/ocr", type="ocr").time():
            # 读取文件内容
            image_data = await file.read()

            result = await multimodal_engine.ocr(
                image_data=image_data,
                language=language,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return result

    except Exception as e:
        logger.error(f"Error in OCR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vision/understand")
async def vision_understand(
    file: UploadFile = File(...),
    prompt: str = "Describe this image in detail.",
    tenant_id: str = None,
    user_id: str = None,
):
    """
    图像理解。

    Args:
        file: 图片文件
        prompt: 提示词
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    global multimodal_engine
    if not multimodal_engine:
        raise HTTPException(status_code=503, detail="Multimodal Engine not initialized")

    REQUEST_COUNT.labels(endpoint="/vision/understand", type="vision").inc()

    try:
        with REQUEST_LATENCY.labels(endpoint="/vision/understand", type="vision").time():
            # 读取文件内容
            image_data = await file.read()

            result = await multimodal_engine.vision_understand(
                image_data=image_data,
                prompt=prompt,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return result

    except Exception as e:
        logger.error(f"Error in vision understanding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vision/detect")
async def vision_detect(
    file: UploadFile = File(...),
    detect_type: str = "objects",  # objects, faces, scenes, text
    tenant_id: str = None,
    user_id: str = None,
):
    """
    图像检测（对象、人脸、场景、文本等）。

    Args:
        file: 图片文件
        detect_type: 检测类型 (objects, faces, scenes, text)
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    global multimodal_engine
    if not multimodal_engine:
        raise HTTPException(status_code=503, detail="Multimodal Engine not initialized")

    REQUEST_COUNT.labels(endpoint="/vision/detect", type="detection").inc()

    try:
        with REQUEST_LATENCY.labels(endpoint="/vision/detect", type="detection").time():
            # 读取文件内容
            image_data = await file.read()

            result = await multimodal_engine.vision_detect(
                image_data=image_data,
                detect_type=detect_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return result

    except Exception as e:
        logger.error(f"Error in vision detection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/video/analyze")
async def video_analyze(
    file: UploadFile = File(...),
    analysis_type: str = "summary",  # summary, keyframes, objects, speech
    tenant_id: str = None,
    user_id: str = None,
):
    """
    视频分析。

    Args:
        file: 视频文件
        analysis_type: 分析类型 (summary, keyframes, objects, speech)
        tenant_id: 租户 ID
        user_id: 用户 ID
    """
    global multimodal_engine
    if not multimodal_engine:
        raise HTTPException(status_code=503, detail="Multimodal Engine not initialized")

    REQUEST_COUNT.labels(endpoint="/video/analyze", type="video").inc()

    try:
        with REQUEST_LATENCY.labels(endpoint="/video/analyze", type="video").time():
            # 读取文件内容
            video_data = await file.read()

            result = await multimodal_engine.video_analyze(
                video_data=video_data,
                analysis_type=analysis_type,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return result

    except Exception as e:
        logger.error(f"Error in video analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """获取 Multimodal Engine 统计信息"""
    global multimodal_engine
    if not multimodal_engine:
        raise HTTPException(status_code=503, detail="Multimodal Engine not initialized")
    return await multimodal_engine.get_stats()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info(
        f"Starting Multimodal Engine server on {host}:{port} with {workers} workers"
    )

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )
