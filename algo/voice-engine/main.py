"""
Voice Engine - 语音处理引擎

核心功能：
- ASR（自动语音识别 - Whisper）
- TTS（文本转语音 - Edge-TTS）
- VAD（语音活动检测 - Silero-VAD）
- 音频预处理
- 流式音频处理
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware

# 添加 common 模块到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

# 导入统一基础设施模块
from cors_config import get_cors_config
from cost_tracking import cost_tracking_middleware
from exception_handlers import register_exception_handlers
from structured_logging import logging_middleware, setup_logging
from telemetry import TracingConfig, init_tracing

# 配置统一日志
setup_logging(service_name="voice-engine")
logger = logging.getLogger(__name__)


# 依赖注入：获取 Voice Engine 实例
def get_voice_engine():  # type: ignore
    """获取 Voice Engine 实例（依赖注入）"""
    if not hasattr(get_voice_engine, "_instance"):
        raise RuntimeError("Voice Engine not initialized")
    return get_voice_engine._instance


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore
    """应用生命周期管理"""
    logger.info("Starting Voice Engine...")

    try:
        # 初始化 OpenTelemetry 追踪
        tracing_config = TracingConfig(
            service_name="voice-engine",
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENV", "development"),
        )
        tracer = init_tracing(tracing_config)
        if tracer:
            logger.info("OpenTelemetry tracing initialized")

        # 初始化 Voice 引擎
        from app.core.voice_engine import VoiceEngine

        voice_engine = VoiceEngine()
        await voice_engine.initialize()

        # 存储为依赖注入实例
        get_voice_engine._instance = voice_engine

        logger.info("Voice Engine started successfully")

        yield

    finally:
        logger.info("Shutting down Voice Engine...")

        # 清理资源
        if hasattr(get_voice_engine, "_instance"):
            await get_voice_engine._instance.cleanup()
            delattr(get_voice_engine, "_instance")

        logger.info("Voice Engine shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Voice Engine",
    description="语音处理引擎 - ASR/TTS/VAD、流式音频处理",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（使用统一配置）
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# 导入配置和中间件
from app.core.config import get_settings
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware

settings = get_settings()

# Redis 客户端初始化
redis_client = None
try:
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
    )
    logger.info(f"Redis client initialized: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except ImportError:
    logger.warning("redis package not installed, rate limiting disabled")
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")

# 幂等性中间件（需要 Redis）
if redis_client:
    app.add_middleware(IdempotencyMiddleware, redis_client=redis_client, ttl=120)
    logger.info("Idempotency middleware enabled")

# 限流中间件
if settings.RATE_LIMIT_ENABLED and redis_client:
    app.add_middleware(
        RateLimiterMiddleware,
        redis_client=redis_client,
        tenant_limit=settings.RATE_LIMIT_TENANT_PER_MINUTE,
        user_limit=settings.RATE_LIMIT_USER_PER_MINUTE,
        ip_limit=settings.RATE_LIMIT_IP_PER_MINUTE,
    )
    logger.info("Rate limiter middleware enabled")
elif settings.RATE_LIMIT_ENABLED and not redis_client:
    logger.warning("Rate limiting disabled: Redis client not available")

# 日志中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

# 成本追踪中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)

# 注册全局异常处理器
register_exception_handlers(app)

# Prometheus 指标
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# 静态文件 (用于测试页面)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files mounted: {static_dir}")

# 注册路由
from app.routers import diarization, emotion, full_duplex, voice_stream

app.include_router(voice_stream.router)
app.include_router(emotion.router)
app.include_router(diarization.router)
app.include_router(full_duplex.router)


@app.get("/health")
async def health_check() -> dict:
    """健康检查"""
    return {"status": "healthy", "service": "voice-engine"}


@app.get("/ready")
async def readiness_check() -> dict:
    """就绪检查"""
    try:
        voice_engine = get_voice_engine()
        checks = {
            "engine": voice_engine is not None,
            "asr": voice_engine.asr_engine is not None if voice_engine else False,
            "tts": voice_engine.tts_engine is not None if voice_engine else False,
            "vad": voice_engine.vad_engine is not None if voice_engine else False,
        }
    except RuntimeError:
        checks = {
            "engine": False,
            "asr": False,
            "tts": False,
            "vad": False,
        }

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
    }


@app.post("/asr")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = "zh",
    model: str = "base",
) -> dict:
    """
    语音识别（ASR）

    Args:
        audio: 音频文件
        language: 语言代码（zh/en/auto）
        model: Whisper 模型（tiny/base/small/medium/large）

    Returns:
        识别文本和详细信息
    """
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # 读取音频数据
        audio_data = await audio.read()

        # 执行语音识别
        result = await voice_engine.speech_to_text(
            audio_data=audio_data,
            language=language,
            model=model,
        )

        return result

    except Exception as e:
        logger.error(f"Error in ASR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tts")
async def text_to_speech(request: dict) -> StreamingResponse:
    """
    文本转语音（TTS）

    Args:
        text: 文本内容
        voice: 语音名称（zh-CN-XiaoxiaoNeural等）
        rate: 语速（-50% ~ +50%）
        pitch: 音调（-50Hz ~ +50Hz）

    Returns:
        音频流
    """
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    text = request.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # 生成音频流
        audio_stream = voice_engine.text_to_speech_stream(
            text=text,
            voice=request.get("voice", "zh-CN-XiaoxiaoNeural"),
            rate=request.get("rate", "+0%"),
            pitch=request.get("pitch", "+0Hz"),
        )

        return StreamingResponse(
            audio_stream,
            media_type="audio/mpeg",
        )

    except Exception as e:
        logger.error(f"Error in TTS: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vad")
async def voice_activity_detection(
    audio: UploadFile = File(...),
    threshold: float = 0.5,
) -> dict:
    """
    语音活动检测（VAD）

    Args:
        audio: 音频文件
        threshold: 检测阈值（0.0 ~ 1.0）

    Returns:
        语音片段列表
    """
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # 读取音频数据
        audio_data = await audio.read()

        # 执行VAD
        segments = await voice_engine.detect_voice_activity(
            audio_data=audio_data,
            threshold=threshold,
        )

        return {
            "segments": segments,
            "count": len(segments),
        }

    except Exception as e:
        logger.error(f"Error in VAD: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process")
async def process_audio(
    audio: UploadFile = File(...),
    operation: str = "asr",
    params: dict | None = None,
) -> dict:
    """
    端到端音频处理

    Args:
        audio: 音频文件
        operation: 操作类型（asr/denoise/enhance）
        params: 操作参数

    Returns:
        处理结果
    """
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if params is None:
        params = {}

    try:
        audio_data = await audio.read()

        if operation == "asr":
            return await voice_engine.speech_to_text(audio_data, **params)
        elif operation == "denoise":
            # 音频降噪处理
            processed_audio = await voice_engine.denoise_audio(audio_data, **params)
            return {
                "audio": processed_audio,
                "format": params.get("output_format", "wav"),
                "sample_rate": settings.AUDIO_SAMPLE_RATE,
            }
        elif operation == "enhance":
            # 音频增强处理（降噪 + 音量标准化）
            enhanced_audio = await voice_engine.enhance_audio(audio_data, **params)
            return {
                "audio": enhanced_audio,
                "format": params.get("output_format", "wav"),
                "sample_rate": settings.AUDIO_SAMPLE_RATE,
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {operation}")

    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices")
async def list_voices() -> dict:
    """列出可用的 TTS 语音"""
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    voices = voice_engine.list_available_voices()

    return {
        "voices": voices,
        "count": len(voices),
    }


@app.get("/stats")
async def get_stats() -> dict:
    """获取统计信息"""
    try:
        voice_engine = get_voice_engine()
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return await voice_engine.get_stats()


# 应用生命周期管理
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("Voice Engine starting up...")

    # 测试 Redis 连接
    if redis_client:
        try:
            await redis_client.ping()
            logger.info("Redis connection verified")
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("Voice Engine shutting down...")

    # 关闭 Redis 连接
    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Failed to close Redis connection: {e}")


if __name__ == "__main__":
    import uvicorn

    # 配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8004"))
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
