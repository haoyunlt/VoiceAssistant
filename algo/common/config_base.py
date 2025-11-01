"""
统一配置管理基类 - 所有服务配置继承此基类
"""

import logging

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class ServiceConfigBase(BaseSettings):
    """服务配置基类 - 包含所有服务通用的配置项"""

    # ===== 服务基础配置 =====
    service_name: str = Field(default="service", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    reload: bool = Field(default=False, env="RELOAD")

    # ===== 日志配置 =====
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
    )

    # ===== 可观测性配置 =====
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=False, env="TRACING_ENABLED")
    tracing_endpoint: str | None = Field(default=None, env="TRACING_ENDPOINT")

    # ===== Redis配置 (可选) =====
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_enabled: bool = Field(default=False, env="REDIS_ENABLED")

    # ===== 缓存配置 =====
    cache_enabled: bool = Field(default=False, env="CACHE_ENABLED")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # 秒

    # ===== 超时与重试配置 =====
    timeout: int = Field(default=30, env="TIMEOUT")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="RETRY_DELAY")

    # ===== 开发模式 =====
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def setup_logging(self):
        """配置日志"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format=self.log_format,
        )
        logger.info(f"Logging configured: level={self.log_level}, service={self.service_name}")


class LLMConfigMixin(BaseSettings):
    """LLM配置混入 - 需要调用LLM的服务使用"""

    # LLM配置
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4", env="LLM_MODEL")
    llm_api_key: str | None = Field(default=None, env="LLM_API_KEY")
    llm_api_base: str | None = Field(default=None, env="LLM_API_BASE")
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    llm_timeout: int = Field(default=30, env="LLM_TIMEOUT")

    # Model Adapter配置（统一LLM路由）
    model_adapter_url: str = Field(default="http://model-adapter:8005", env="MODEL_ADAPTER_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class VectorStoreConfigMixin(BaseSettings):
    """向量存储配置混入 - 需要向量操作的服务使用"""

    # Vector Store Adapter配置
    vector_store_adapter_url: str = Field(
        default="http://vector-store-adapter:8003", env="VECTOR_STORE_ADAPTER_URL"
    )
    vector_collection_name: str = Field(default="document_chunks", env="VECTOR_COLLECTION_NAME")
    vector_backend: str = Field(default="milvus", env="VECTOR_BACKEND")

    # 向量检索配置
    vector_top_k: int = Field(default=10, env="VECTOR_TOP_K")
    vector_timeout: float = Field(default=30.0, env="VECTOR_TIMEOUT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class RetrievalConfigMixin(BaseSettings):
    """检索服务配置混入 - 需要调用检索服务的服务使用"""

    # Retrieval Service配置
    retrieval_service_url: str = Field(
        default="http://retrieval-service:8012", env="RETRIEVAL_SERVICE_URL"
    )
    retrieval_mode: str = Field(default="hybrid", env="RETRIEVAL_MODE")
    retrieval_top_k: int = Field(default=5, env="RETRIEVAL_TOP_K")
    retrieval_timeout: int = Field(default=10, env="RETRIEVAL_TIMEOUT")
    rerank_enabled: bool = Field(default=True, env="RERANK_ENABLED")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
