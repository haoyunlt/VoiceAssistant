"""
Configuration management for Multimodal Engine
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_NAME: str = "multimodal-engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8005

    # OCR 配置
    OCR_PROVIDER: str = "paddleocr"  # paddleocr, easyocr, tesseract
    OCR_LANGUAGES: str = "ch,en"  # 支持的语言
    OCR_USE_GPU: bool = False  # 是否使用 GPU
    OCR_CONFIDENCE_THRESHOLD: float = 0.5  # 置信度阈值

    # PaddleOCR 配置
    PADDLE_DET_MODEL: str = "ch_PP-OCRv4_det"
    PADDLE_REC_MODEL: str = "ch_PP-OCRv4_rec"
    PADDLE_CLS_MODEL: str = "ch_ppocr_mobile_v2.0_cls"

    # Vision LLM 配置
    VISION_PROVIDER: str = "gpt4v"  # gpt4v, claude3
    VISION_MODEL: str = "gpt-4-vision-preview"
    VISION_MAX_TOKENS: int = 1000
    MODEL_ADAPTER_ENDPOINT: str = "http://model-adapter:8006"

    # 图像处理配置
    MAX_IMAGE_SIZE: int = 4096  # 最大图像尺寸（像素）
    RESIZE_QUALITY: int = 95  # 压缩质量
    SUPPORTED_FORMATS: str = "jpg,jpeg,png,bmp,tiff,pdf"

    # MinIO 对象存储配置
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "multimodal-files"
    MINIO_SECURE: bool = False

    # Redis 缓存配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 5
    CACHE_TTL: int = 3600  # 1小时

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # OpenTelemetry 配置
    OTEL_ENABLED: bool = False
    OTEL_ENDPOINT: str = "http://jaeger:4317"
    OTEL_SERVICE_NAME: str = "multimodal-engine"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
