"""
Configuration - 服务配置
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """服务配置"""

    # 服务基本信息
    APP_NAME: str = "Knowledge Service"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8006
    ENVIRONMENT: str = "development"

    # Neo4j 配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_MAX_CONNECTION_LIFETIME: int = 3600  # 1小时
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50
    NEO4J_CONNECTION_TIMEOUT: int = 30  # 30秒
    NEO4J_MAX_TRANSACTION_RETRY_TIME: int = 30  # 30秒

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

    # Kafka 配置
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_KNOWLEDGE_EVENTS: str = "knowledge.events"
    KAFKA_ACKS: str = "all"
    KAFKA_RETRIES: int = 3
    KAFKA_LINGER_MS: int = 5
    KAFKA_COMPRESSION_TYPE: str = "gzip"

    # SpaCy 模型
    SPACY_MODEL: str = "en_core_web_sm"  # 或 zh_core_web_sm

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # CORS 配置
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # 限流配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # 清理任务配置
    CLEANUP_INTERVAL_HOURS: int = 24
    CLEANUP_ORPHAN_DAYS_THRESHOLD: int = 30
    CLEANUP_COMMUNITY_DAYS_THRESHOLD: int = 7

    # OpenTelemetry 配置
    OTEL_ENABLED: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "knowledge-service"

    # 健康检查配置
    HEALTH_CHECK_INTERVAL: int = 30  # 秒

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局配置实例
settings = Settings()

