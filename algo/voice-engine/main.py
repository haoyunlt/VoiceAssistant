"""
Voice Engine - FastAPI Application

语音引擎服务（ASR / TTS / VAD）
"""

from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.routers import asr, health, tts, vad
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 设置日志
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"ASR Provider: {settings.ASR_PROVIDER}")
    print(f"TTS Provider: {settings.TTS_PROVIDER}")
    print(f"VAD Enabled: {settings.VAD_ENABLED}")

    yield

    # 关闭时
    print(f"Shutting down {settings.APP_NAME}")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="语音引擎服务（ASR / TTS / VAD）",
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


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# 注册路由
app.include_router(health.router)
app.include_router(asr.router)
app.include_router(tts.router)
app.include_router(vad.router)


# 根路径
@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "asr": "/api/v1/asr",
            "tts": "/api/v1/tts",
            "vad": "/api/v1/vad",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
