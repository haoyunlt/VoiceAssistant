"""
Configuration management for Voice Engine
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_NAME: str = "voice-engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8004

    # ASR（自动语音识别）配置
    ASR_PROVIDER: str = "whisper"  # whisper, azure
    WHISPER_MODEL: str = "base"  # tiny, base, small, medium, large
    WHISPER_DEVICE: str = "cpu"  # cpu, cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8, float16, float32

    # Azure Speech 配置（可选）
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = "eastasia"

    # 多厂商语音服务配置
    PREFERRED_ASR: str = "faster-whisper"  # azure, faster-whisper
    PREFERRED_TTS: str = "edge"  # azure, edge

    # TTS（文本转语音）配置
    TTS_PROVIDER: str = "edge"  # edge, azure
    TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"  # 默认中文女声
    TTS_RATE: str = "+0%"  # 语速调整
    TTS_PITCH: str = "+0Hz"  # 音调调整

    # VAD（语音活动检测）配置
    VAD_ENABLED: bool = True
    VAD_THRESHOLD: float = 0.3  # 噪声门限 (0-1)
    VAD_MIN_SPEECH_DURATION_MS: int = 500  # 最小语音段（毫秒）
    VAD_MIN_SILENCE_DURATION_MS: int = 2000  # 静音超时（毫秒）
    VAD_SPEECH_PAD_MS: int = 400  # 语音填充（毫秒）

    # 音频格式配置
    AUDIO_SAMPLE_RATE: int = 16000  # 采样率（Hz）
    AUDIO_CHANNELS: int = 1  # 单声道
    AUDIO_FORMAT: str = "wav"  # wav, mp3, opus

    # MinIO 对象存储配置（用于音频文件存储）
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "voice-files"
    MINIO_SECURE: bool = False

    # Redis 缓存配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 4
    TTS_CACHE_TTL: int = 86400  # TTS 缓存 24 小时

    @property
    def REDIS_URL(self) -> str:
        """生成 Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # OpenTelemetry 配置
    OTEL_ENABLED: bool = False
    OTEL_ENDPOINT: str = "http://jaeger:4317"
    OTEL_SERVICE_NAME: str = "voice-engine"

    # 性能配置
    MAX_AUDIO_DURATION_SECONDS: int = 300  # 最大音频时长（5分钟）
    ASR_CHUNK_SIZE: int = 1024  # ASR 流式处理块大小

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
