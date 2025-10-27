"""
Configuration - 服务配置
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """服务配置"""

    # 服务基本信息
    APP_NAME: str = "Knowledge Service"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8006

    # Neo4j 配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # SpaCy 模型
    SPACY_MODEL: str = "en_core_web_sm"  # 或 zh_core_web_sm

    # 日志配置
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()

