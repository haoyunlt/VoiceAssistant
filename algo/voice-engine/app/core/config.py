"""
Configuration management for Voice Engine
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_NAME: str = "voice-engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8004, ge=1, le=65535)

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
    VAD_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)  # 噪声门限 (0-1)
    VAD_MIN_SPEECH_DURATION_MS: int = Field(default=500, ge=0)  # 最小语音段（毫秒）
    VAD_MIN_SILENCE_DURATION_MS: int = Field(default=2000, ge=0)  # 静音超时（毫秒）
    VAD_SPEECH_PAD_MS: int = Field(default=400, ge=0)  # 语音填充（毫秒）

    # 音频格式配置
    AUDIO_SAMPLE_RATE: int = Field(default=16000, ge=8000, le=48000)  # 采样率（Hz）
    AUDIO_CHANNELS: int = Field(default=1, ge=1, le=2)  # 单声道/立体声
    AUDIO_FORMAT: str = Field(default="wav", pattern="^(wav|mp3|opus)$")  # wav, mp3, opus

    # MinIO 对象存储配置（用于音频文件存储）
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "voice-files"
    MINIO_SECURE: bool = False

    # Redis 缓存配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = Field(default=6379, ge=1, le=65535)
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = Field(default=4, ge=0, le=15)
    TTS_CACHE_TTL: int = Field(default=86400, ge=60)  # TTS 缓存 24 小时（最少1分钟）

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
    MAX_AUDIO_DURATION_SECONDS: int = Field(default=300, ge=1, le=3600)  # 最大音频时长（5分钟）
    ASR_CHUNK_SIZE: int = Field(default=1024, ge=256, le=8192)  # ASR 流式处理块大小

    # 超时配置
    ASR_TIMEOUT_SECONDS: int = Field(default=60, ge=5)  # ASR 超时
    TTS_TIMEOUT_SECONDS: int = Field(default=30, ge=5)  # TTS 超时
    VAD_TIMEOUT_SECONDS: int = Field(default=10, ge=1)  # VAD 超时

    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_TENANT_PER_MINUTE: int = Field(default=100, ge=1)
    RATE_LIMIT_USER_PER_MINUTE: int = Field(default=20, ge=1)
    RATE_LIMIT_IP_PER_MINUTE: int = Field(default=10, ge=1)

    # 熔断器配置
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=5, ge=1)
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = Field(default=60, ge=1)

    @field_validator("WHISPER_MODEL")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        """验证 Whisper 模型"""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if v not in valid_models:
            raise ValueError(f"Invalid WHISPER_MODEL: {v}. Must be one of {valid_models}")
        return v

    @field_validator("WHISPER_DEVICE")
    @classmethod
    def validate_device(cls, v: str) -> str:
        """验证设备"""
        valid_devices = ["cpu", "cuda", "auto"]
        if v not in valid_devices:
            raise ValueError(f"Invalid WHISPER_DEVICE: {v}. Must be one of {valid_devices}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
