"""
RAG Engine 配置管理
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class RAGConfig(BaseSettings):
    """RAG Engine 配置"""

    # 服务配置
    service_name: str = Field(default="rag-engine", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8006, env="PORT", ge=1, le=65535)
    workers: int = Field(default=1, env="WORKERS", ge=1, le=16)
    reload: bool = Field(default=False, env="RELOAD")

    # LLM配置
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-3.5-turbo", env="LLM_MODEL")
    llm_api_key: Optional[str] = Field(default=None, env="LLM_API_KEY")
    llm_api_base: Optional[str] = Field(
        default="http://model-adapter:8005/api/v1",
        env="LLM_API_BASE"
    )
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE", ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS", ge=1, le=32000)
    llm_timeout: int = Field(default=30, env="LLM_TIMEOUT", ge=1)

    # Retrieval配置
    retrieval_service_url: str = Field(
        default="http://retrieval-service:8012", env="RETRIEVAL_SERVICE_URL"
    )
    retrieval_mode: str = Field(default="hybrid", env="RETRIEVAL_MODE")
    retrieval_top_k: int = Field(default=5, env="RETRIEVAL_TOP_K", ge=1, le=100)
    retrieval_timeout: int = Field(default=10, env="RETRIEVAL_TIMEOUT", ge=1)
    rerank_enabled: bool = Field(default=True, env="RERANK_ENABLED")

    # 查询改写配置
    query_rewrite_enabled: bool = Field(default=True, env="QUERY_REWRITE_ENABLED")
    query_rewrite_model: str = Field(
        default="gpt-3.5-turbo", env="QUERY_REWRITE_MODEL"
    )

    # 缓存配置
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # 秒
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 性能配置
    timeout: int = Field(default=30, env="RAG_TIMEOUT")
    max_retries: int = Field(default=3, env="RAG_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="RAG_RETRY_DELAY")

    # 上下文配置
    max_context_tokens: int = Field(default=4000, env="MAX_CONTEXT_TOKENS")
    context_compression_enabled: bool = Field(
        default=False, env="CONTEXT_COMPRESSION_ENABLED"
    )

    # Observability
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=False, env="TRACING_ENABLED")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # 开发模式
    debug: bool = Field(default=False, env="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
_config: Optional[RAGConfig] = None


def get_config() -> RAGConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = RAGConfig()
    return _config


def reload_config() -> RAGConfig:
    """重新加载配置"""
    global _config
    _config = RAGConfig()
    return _config
