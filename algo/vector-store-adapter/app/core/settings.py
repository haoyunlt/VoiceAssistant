"""配置管理 - 使用 Pydantic Settings"""

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务配置
    service_name: str = Field(default="vector-store-adapter", description="服务名称")
    version: str = Field(default="1.0.0", description="版本")
    host: str = Field(default="0.0.0.0", description="服务主机")
    port: int = Field(default=8003, description="服务端口")
    workers: int = Field(default=1, description="工作进程数", ge=1)
    reload: bool = Field(default=False, description="热重载")
    log_level: str = Field(default="INFO", description="日志级别")

    # Milvus 配置
    milvus_host: str = Field(default="localhost", description="Milvus 主机")
    milvus_port: int = Field(default=19530, description="Milvus 端口")
    milvus_user: str = Field(default="", description="Milvus 用户名")
    milvus_password: str = Field(default="", description="Milvus 密码")

    # PostgreSQL (pgvector) 配置
    pgvector_host: str = Field(default="localhost", description="PostgreSQL 主机")
    pgvector_port: int = Field(default=5432, description="PostgreSQL 端口")
    pgvector_database: str = Field(default="voiceassistant", description="数据库名称")
    pgvector_user: str = Field(default="postgres", description="数据库用户")
    pgvector_password: str = Field(default="", description="数据库密码")
    pgvector_min_pool_size: int = Field(default=2, description="最小连接池大小", ge=1)
    pgvector_max_pool_size: int = Field(default=10, description="最大连接池大小", ge=1)

    # Redis 配置（用于限流和幂等性）
    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, description="Redis 端口")
    redis_db: int = Field(default=0, description="Redis 数据库", ge=0)
    redis_password: str = Field(default="", description="Redis 密码")

    # 默认配置
    default_backend: str = Field(default="milvus", description="默认后端")
    vector_dimension: int = Field(default=1024, description="向量维度", ge=1)

    # 限流配置
    rate_limit_enabled: bool = Field(default=True, description="是否启用限流")
    rate_limit_requests: int = Field(default=100, description="限流请求数", ge=1)
    rate_limit_window: int = Field(default=60, description="限流时间窗口（秒）", ge=1)

    # 幂等性配置
    idempotency_enabled: bool = Field(default=True, description="是否启用幂等性")
    idempotency_ttl: int = Field(default=120, description="幂等性TTL（秒）", ge=1)

    # OpenTelemetry 配置
    otel_enabled: bool = Field(default=False, description="是否启用 OpenTelemetry")
    otel_endpoint: str = Field(default="http://localhost:4317", description="OTLP 端点")
    otel_service_name: str = Field(default="vector-store-adapter", description="服务名称")

    def get_backend_config(self, backend: str) -> dict[str, Any]:
        """获取特定后端的配置"""
        if backend == "milvus":
            return {
                "host": self.milvus_host,
                "port": self.milvus_port,
                "user": self.milvus_user,
                "password": self.milvus_password,
            }
        elif backend == "pgvector":
            return {
                "host": self.pgvector_host,
                "port": self.pgvector_port,
                "database": self.pgvector_database,
                "user": self.pgvector_user,
                "password": self.pgvector_password,
                "min_pool_size": self.pgvector_min_pool_size,
                "max_pool_size": self.pgvector_max_pool_size,
            }
        else:
            raise ValueError(f"Unknown backend: {backend}")


# 全局配置实例
settings = Settings()
