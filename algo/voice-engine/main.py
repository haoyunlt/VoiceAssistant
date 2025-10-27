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
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局变量
voice_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global voice_engine

    logger.info("Starting Voice Engine...")

    try:
        # 初始化 Voice 引擎
        from app.core.voice_engine import VoiceEngine

        voice_engine = VoiceEngine()
        await voice_engine.initialize()

        logger.info("Voice Engine started successfully")

        yield

    finally:
        logger.info("Shutting down Voice Engine...")

        # 清理资源
        if voice_engine:
            await voice_engine.cleanup()

        logger.info("Voice Engine shut down complete")


# 创建 FastAPI 应用
app = FastAPI(
    title="Voice Engine",
    description="语音处理引擎 - ASR/TTS/VAD、流式音频处理",
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
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "voice-engine"}


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    global voice_engine

    checks = {
        "engine": voice_engine is not None,
        "asr": voice_engine.asr_engine is not None if voice_engine else False,
        "tts": voice_engine.tts_engine is not None if voice_engine else False,
        "vad": voice_engine.vad_engine is not None if voice_engine else False,
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
):
    """
    语音识别（ASR）

    Args:
        audio: 音频文件
        language: 语言代码（zh/en/auto）
        model: Whisper 模型（tiny/base/small/medium/large）

    Returns:
        识别文本和详细信息
    """
    global voice_engine

    if not voice_engine:
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
async def text_to_speech(request: dict):
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
    global voice_engine

    if not voice_engine:
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
):
    """
    语音活动检测（VAD）

    Args:
        audio: 音频文件
        threshold: 检测阈值（0.0 ~ 1.0）

    Returns:
        语音片段列表
    """
    global voice_engine

    if not voice_engine:
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
    params: dict = None,
):
    """
    端到端音频处理

    Args:
        audio: 音频文件
        operation: 操作类型（asr/denoise/enhance）
        params: 操作参数

    Returns:
        处理结果
    """
    global voice_engine

    if not voice_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if params is None:
        params = {}

    try:
        audio_data = await audio.read()

        if operation == "asr":
            return await voice_engine.speech_to_text(audio_data, **params)
        elif operation == "denoise":
            # TODO: 实现降噪
            raise HTTPException(status_code=501, detail="Denoise not yet implemented")
        elif operation == "enhance":
            # TODO: 实现音频增强
            raise HTTPException(status_code=501, detail="Enhance not yet implemented")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {operation}")

    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices")
async def list_voices():
    """列出可用的 TTS 语音"""
    global voice_engine

    if not voice_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    voices = voice_engine.list_available_voices()

    return {
        "voices": voices,
        "count": len(voices),
    }


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    global voice_engine

    if not voice_engine:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return await voice_engine.get_stats()


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
