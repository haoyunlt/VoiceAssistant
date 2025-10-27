"""
Configuration management for Retrieval Service
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    APP_NAME: str = "retrieval-service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8003

    # Milvus 向量数据库配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_COLLECTION: str = "documents"

    # Elasticsearch 配置（BM25 检索）
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    ELASTICSEARCH_USER: str = ""
    ELASTICSEARCH_PASSWORD: str = ""
    ELASTICSEARCH_INDEX: str = "documents"

    # 检索配置
    VECTOR_TOP_K: int = 50
    BM25_TOP_K: int = 50
    HYBRID_TOP_K: int = 20
    RERANK_TOP_K: int = 10

    # 重排序配置
    ENABLE_RERANK: bool = True
    RERANK_MODEL: str = "cross-encoder"  # cross-encoder, llm
    CROSS_ENCODER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"

    # LLM 重排序配置（如果使用）
    LLM_RERANK_ENDPOINT: str = "http://model-adapter:8006"
    LLM_RERANK_MODEL: str = "gpt-4"

    # RRF（Reciprocal Rank Fusion）参数
    RRF_K: int = 60

    # Neo4j 图数据库配置
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MAX_CONNECTION_LIFETIME: int = 3600
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50

    # Graph 检索配置
    GRAPH_TOP_K: int = 50
    GRAPH_DEPTH: int = 2  # 图谱查询深度（跳数）
    ENABLE_GRAPH_RETRIEVAL: bool = True

    # 混合图谱检索权重配置
    HYBRID_VECTOR_WEIGHT: float = 0.5
    HYBRID_BM25_WEIGHT: float = 0.2
    HYBRID_GRAPH_WEIGHT: float = 0.3

    # 日志配置
    LOG_LEVEL: str = "INFO"

    # OpenTelemetry 配置
    OTEL_ENABLED: bool = False
    OTEL_ENDPOINT: str = "http://jaeger:4317"
    OTEL_SERVICE_NAME: str = "retrieval-service"

    # Redis 缓存配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 3
    CACHE_TTL: int = 3600  # 1小时

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
