"""配置管理"""
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    SERVICE_NAME: str = "agent-engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8003, env="PORT")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS配置
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # AI模型配置
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1", env="OPENAI_API_BASE")
    DEFAULT_MODEL: str = Field(default="gpt-4", env="DEFAULT_MODEL")
    MAX_TOKENS: int = Field(default=4096, env="MAX_TOKENS")
    TEMPERATURE: float = Field(default=0.7, env="TEMPERATURE")

    # Agent配置
    MAX_ITERATIONS: int = Field(default=10, env="MAX_ITERATIONS")
    TIMEOUT_SECONDS: int = Field(default=300, env="TIMEOUT_SECONDS")

    # Redis配置（可选，用于缓存）
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 数据库配置（如需持久化）
    DATABASE_URL: str = Field(
        default="postgresql://voicehelper:voicehelper_dev@localhost:5432/voicehelper",
        env="DATABASE_URL"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
