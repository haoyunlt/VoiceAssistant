"""
统一配置管理
基于 Pydantic 的配置验证和管理
"""

import os

try:
    from pydantic import BaseSettings, Field, validator
    PYDANTIC_V1 = True
except ImportError:
    # Pydantic v2
    from pydantic import Field
    from pydantic import field_validator as validator
    from pydantic_settings import BaseSettings
    PYDANTIC_V1 = False


class ServiceConfig(BaseSettings):
    """
    服务配置基类
    所有服务的通用配置
    """

    # 基础配置
    service_name: str = Field(description="服务名称")
    service_port: int = Field(default=8000, ge=1000, le=65535, description="服务端口")
    service_host: str = Field(default="0.0.0.0", description="服务主机")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(default="json", description="日志格式: json|text")

    # 可观测性配置
    otel_enabled: bool = Field(default=True, description="是否启用 OpenTelemetry")
    otel_endpoint: str = Field(default="http://localhost:4317", description="OTEL Collector 端点")
    otel_service_name: str | None = Field(default=None, description="OTEL 服务名（默认使用 service_name）")
    metrics_enabled: bool = Field(default=True, description="是否启用指标")
    tracing_enabled: bool = Field(default=True, description="是否启用追踪")

    # 性能配置
    max_workers: int = Field(default=10, ge=1, le=100, description="最大工作线程数")
    request_timeout: int = Field(default=30, ge=1, le=300, description="请求超时（秒）")
    graceful_shutdown_timeout: int = Field(default=30, ge=1, description="优雅关闭超时（秒）")

    # 健康检查
    health_check_enabled: bool = Field(default=True, description="是否启用健康检查")

    # 环境
    environment: str = Field(default="development", description="运行环境: development|staging|production")

    if PYDANTIC_V1:
        @validator('log_level')
        def validate_log_level(cls, v):
            """验证日志级别"""
            allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            v_upper = v.upper()
            if v_upper not in allowed:
                raise ValueError(f'log_level must be one of {allowed}')
            return v_upper

        @validator('log_format')
        def validate_log_format(cls, v):
            """验证日志格式"""
            allowed = ['json', 'text']
            v_lower = v.lower()
            if v_lower not in allowed:
                raise ValueError(f'log_format must be one of {allowed}')
            return v_lower

        @validator('environment')
        def validate_environment(cls, v):
            """验证环境"""
            allowed = ['development', 'staging', 'production']
            v_lower = v.lower()
            if v_lower not in allowed:
                raise ValueError(f'environment must be one of {allowed}')
            return v_lower

        @validator('otel_service_name', always=True)
        def set_otel_service_name(cls, v, values):
            """设置 OTEL 服务名（默认使用 service_name）"""
            return v or values.get('service_name')

        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        # Pydantic v2
        @validator('log_level')
        @classmethod
        def validate_log_level(cls, v):
            allowed = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            v_upper = v.upper()
            if v_upper not in allowed:
                raise ValueError(f'log_level must be one of {allowed}')
            return v_upper

        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }

    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == 'production'

    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == 'development'


class LLMConfig(BaseSettings):
    """LLM 服务配置"""

    llm_provider: str = Field(default="openai", description="LLM 提供商")
    llm_model: str = Field(default="gpt-3.5-turbo", description="LLM 模型")
    llm_api_key: str | None = Field(default=None, description="LLM API 密钥")
    llm_api_base: str | None = Field(default=None, description="LLM API 基础 URL")
    llm_timeout: int = Field(default=60, ge=1, description="LLM 请求超时（秒）")
    llm_max_retries: int = Field(default=3, ge=0, description="LLM 最大重试次数")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM 温度")
    llm_max_tokens: int = Field(default=2000, ge=1, description="LLM 最大 token 数")

    if PYDANTIC_V1:
        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    db_host: str = Field(default="localhost", description="数据库主机")
    db_port: int = Field(default=5432, ge=1, le=65535, description="数据库端口")
    db_user: str = Field(default="postgres", description="数据库用户")
    db_password: str = Field(default="", description="数据库密码")
    db_database: str = Field(default="voiceassistant", description="数据库名称")
    db_pool_size: int = Field(default=10, ge=1, description="连接池大小")
    db_max_overflow: int = Field(default=20, ge=0, description="连接池最大溢出")
    db_pool_timeout: int = Field(default=30, ge=1, description="连接池超时（秒）")
    db_echo: bool = Field(default=False, description="是否打印 SQL")

    if PYDANTIC_V1:
        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }

    def get_database_url(self) -> str:
        """获取数据库 URL"""
        return (
            f"postgresql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_database}"
        )


class RedisConfig(BaseSettings):
    """Redis 配置"""

    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis 端口")
    redis_password: str | None = Field(default=None, description="Redis 密码")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis 数据库")
    redis_pool_size: int = Field(default=10, ge=1, description="连接池大小")
    redis_timeout: int = Field(default=5, ge=1, description="连接超时（秒）")

    if PYDANTIC_V1:
        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }

    def get_redis_url(self) -> str:
        """获取 Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


class VectorStoreConfig(BaseSettings):
    """向量库配置"""

    vector_store_type: str = Field(default="milvus", description="向量库类型: milvus|qdrant|weaviate")
    vector_store_host: str = Field(default="localhost", description="向量库主机")
    vector_store_port: int = Field(default=19530, ge=1, le=65535, description="向量库端口")
    vector_store_collection: str = Field(default="documents", description="集合名称")
    vector_dimension: int = Field(default=1536, ge=1, description="向量维度")
    vector_metric_type: str = Field(default="IP", description="距离度量: IP|L2|COSINE")

    if PYDANTIC_V1:
        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch 配置"""

    elasticsearch_host: str = Field(default="localhost", description="ES 主机")
    elasticsearch_port: int = Field(default=9200, ge=1, le=65535, description="ES 端口")
    elasticsearch_username: str | None = Field(default=None, description="ES 用户名")
    elasticsearch_password: str | None = Field(default=None, description="ES 密码")
    elasticsearch_timeout: int = Field(default=30, ge=1, description="ES 超时（秒）")
    elasticsearch_max_retries: int = Field(default=3, ge=0, description="ES 最大重试次数")
    elasticsearch_pool_size: int = Field(default=25, ge=1, description="连接池大小")

    if PYDANTIC_V1:
        class Config:
            env_file = '.env'
            env_file_encoding = 'utf-8'
            case_sensitive = False
    else:
        model_config = {
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "case_sensitive": False,
        }


# ==================== 工具函数 ====================

def load_config(config_class: type, env_file: str | None = None) -> BaseSettings:
    """
    加载配置

    Args:
        config_class: 配置类
        env_file: 环境文件路径（可选）

    Returns:
        配置实例
    """
    if env_file and os.path.exists(env_file):
        if PYDANTIC_V1:
            return config_class(_env_file=env_file)
        else:
            # Pydantic v2
            return config_class(_env_file=env_file)
    return config_class()


def merge_configs(*configs: BaseSettings) -> dict:
    """
    合并多个配置为字典

    Args:
        *configs: 配置实例

    Returns:
        合并后的配置字典
    """
    result = {}
    for config in configs:
        if PYDANTIC_V1:
            result.update(config.dict())
        else:
            result.update(config.model_dump())
    return result
