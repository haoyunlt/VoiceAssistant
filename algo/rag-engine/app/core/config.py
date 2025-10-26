"""配置管理"""
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    SERVICE_NAME: str = "rag-engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8006, env="PORT")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS配置
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # 检索服务配置
    RETRIEVAL_SERVICE_URL: str = Field(
        default="http://localhost:8007", env="RETRIEVAL_SERVICE_URL"
    )
    RETRIEVAL_TOP_K: int = Field(default=10, env="RETRIEVAL_TOP_K")

    # 模型适配器配置
    MODEL_ADAPTER_URL: str = Field(
        default="http://localhost:8005", env="MODEL_ADAPTER_URL"
    )

    # LLM配置
    DEFAULT_LLM_MODEL: str = Field(default="gpt-4", env="DEFAULT_LLM_MODEL")
    LLM_TEMPERATURE: float = Field(default=0.7, env="LLM_TEMPERATURE")
    LLM_MAX_TOKENS: int = Field(default=2048, env="LLM_MAX_TOKENS")

    # RAG配置
    MAX_CONTEXT_LENGTH: int = Field(default=4000, env="MAX_CONTEXT_LENGTH")
    ENABLE_RERANK: bool = Field(default=True, env="ENABLE_RERANK")
    RERANK_TOP_K: int = Field(default=5, env="RERANK_TOP_K")
    ENABLE_QUERY_EXPANSION: bool = Field(default=True, env="ENABLE_QUERY_EXPANSION")
    ENABLE_SEMANTIC_CACHE: bool = Field(default=True, env="ENABLE_SEMANTIC_CACHE")

    # 提示词模板
    DEFAULT_SYSTEM_PROMPT: str = Field(
        default="You are a helpful AI assistant. Answer the user's question based on the provided context.",
        env="DEFAULT_SYSTEM_PROMPT",
    )

    # Redis配置（用于缓存）
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")

    # 数据库配置（可选）
    DATABASE_URL: str = Field(
        default="postgresql://voicehelper:voicehelper_dev@localhost:5432/voicehelper",
        env="DATABASE_URL",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
