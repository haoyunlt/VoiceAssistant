"""
统一的配置验证模式

使用 Pydantic 进行配置验证和类型安全，支持：
- 环境变量自动加载
- 类型验证
- 默认值
- 自定义验证器
"""


from pydantic import Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseSettings):
    """
    服务基础配置

    所有Python服务的通用配置项
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 服务基本信息 ===
    service_name: str = Field(..., description="服务名称")
    service_version: str = Field(default="1.0.0", description="服务版本")
    environment: str = Field(default="development", description="环境（dev/staging/prod）")

    # === 服务端口配置 ===
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, ge=1024, le=65535, description="监听端口")
    workers: int = Field(default=1, ge=1, le=32, description="Worker 进程数")
    reload: bool = Field(default=False, description="热重载模式（仅开发）")

    # === 日志配置 ===
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(default="json", description="日志格式（json/text）")

    # === CORS 配置 ===
    cors_origins: str = Field(default="", description="CORS 源列表（逗号分隔）")
    cors_allow_credentials: bool = Field(default=True, description="是否允许凭证")
    cors_max_age: int = Field(default=3600, ge=0, description="预检请求缓存时间")

    # === OpenTelemetry 配置 ===
    otel_enabled: bool = Field(default=False, description="是否启用追踪")
    otel_endpoint: str = Field(default="localhost:4317", description="OTLP 端点")
    otel_sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="采样率")

    # === 认证配置 ===
    auth_enabled: bool = Field(default=False, description="是否启用认证")
    auth_fail_open: bool = Field(default=False, description="认证服务不可用时降级")
    identity_service_url: HttpUrl | None = Field(
        default=None, description="身份认证服务URL"
    )

    # === 成本配置 ===
    daily_cost_limit_usd: float = Field(
        default=1000.0, ge=0, description="日成本上限（美元）"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """验证环境"""
        valid_envs = ["development", "dev", "staging", "production", "prod"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        # 标准化
        if v_lower in ["dev"]:
            return "development"
        if v_lower in ["prod"]:
            return "production"
        return v_lower

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """验证日志格式"""
        valid_formats = ["json", "text"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v_lower

    @model_validator(mode="after")
    def validate_production_settings(self):
        """验证生产环境设置"""
        if self.environment == "production":
            # 生产环境必须启用追踪
            if not self.otel_enabled:
                raise ValueError("OpenTelemetry must be enabled in production")

            # 生产环境必须配置CORS
            if not self.cors_origins:
                raise ValueError("CORS origins must be configured in production")

            # 生产环境禁止热重载
            if self.reload:
                raise ValueError("Hot reload must be disabled in production")

            # 生产环境日志必须是JSON
            if self.log_format != "json":
                raise ValueError("Log format must be 'json' in production")

        return self

    def get_cors_origins_list(self) -> list[str]:
        """获取 CORS 源列表"""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    model_config = SettingsConfigDict(env_prefix="DB_", case_sensitive=False)

    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, ge=1, le=65535, description="数据库端口")
    database: str = Field(..., description="数据库名称")
    username: str = Field(..., description="数据库用户名")
    password: str = Field(..., description="数据库密码")
    pool_size: int = Field(default=10, ge=1, le=100, description="连接池大小")
    max_overflow: int = Field(default=20, ge=0, le=100, description="连接池最大溢出")
    pool_timeout: float = Field(default=30.0, ge=1.0, description="连接池超时")

    @property
    def url(self) -> str:
        """生成数据库URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseSettings):
    """Redis 配置"""

    model_config = SettingsConfigDict(env_prefix="REDIS_", case_sensitive=False)

    host: str = Field(default="localhost", description="Redis 主机")
    port: int = Field(default=6379, ge=1, le=65535, description="Redis 端口")
    password: str | None = Field(default=None, description="Redis 密码")
    db: int = Field(default=0, ge=0, le=15, description="Redis 数据库编号")
    max_connections: int = Field(default=50, ge=1, le=1000, description="最大连接数")
    socket_timeout: float = Field(default=5.0, ge=0.1, description="Socket 超时")
    socket_connect_timeout: float = Field(default=5.0, ge=0.1, description="连接超时")

    @property
    def url(self) -> str:
        """生成 Redis URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MilvusConfig(BaseSettings):
    """Milvus 配置"""

    model_config = SettingsConfigDict(env_prefix="MILVUS_", case_sensitive=False)

    host: str = Field(default="localhost", description="Milvus 主机")
    port: int = Field(default=19530, ge=1, le=65535, description="Milvus 端口")
    collection_name: str = Field(..., description="集合名称")
    index_type: str = Field(default="IVF_FLAT", description="索引类型")
    metric_type: str = Field(default="L2", description="距离度量")
    nlist: int = Field(default=128, ge=1, description="聚类中心数")

    @field_validator("metric_type")
    @classmethod
    def validate_metric_type(cls, v: str) -> str:
        """验证距离度量类型"""
        valid_metrics = ["L2", "IP", "COSINE"]
        v_upper = v.upper()
        if v_upper not in valid_metrics:
            raise ValueError(f"Invalid metric type: {v}. Must be one of {valid_metrics}")
        return v_upper


class LLMConfig(BaseSettings):
    """LLM 配置"""

    model_config = SettingsConfigDict(env_prefix="LLM_", case_sensitive=False)

    provider: str = Field(default="openai", description="LLM 提供商")
    model: str = Field(default="gpt-3.5-turbo", description="模型名称")
    api_key: str | None = Field(default=None, description="API Key")
    api_base: HttpUrl | None = Field(default=None, description="API Base URL")
    max_tokens: int = Field(default=2048, ge=1, le=128000, description="最大 Token 数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    timeout: float = Field(default=60.0, ge=1.0, description="超时时间")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """验证 LLM 提供商"""
        valid_providers = ["openai", "anthropic", "azure", "zhipu", "qwen"]
        v_lower = v.lower()
        if v_lower not in valid_providers:
            raise ValueError(
                f"Invalid LLM provider: {v}. Must be one of {valid_providers}"
            )
        return v_lower


class VoiceEngineConfig(ServiceConfig):
    """Voice Engine 特定配置"""

    # 继承基础服务配置
    service_name: str = Field(default="voice-engine", description="服务名称")
    port: int = Field(default=8004, ge=1024, le=65535, description="监听端口")

    # Voice Engine 特定配置
    whisper_model: str = Field(default="base", description="Whisper 模型")
    tts_voice: str = Field(default="zh-CN-XiaoxiaoNeural", description="TTS 语音")
    sample_rate: int = Field(default=16000, ge=8000, le=48000, description="采样率")
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="VAD 阈值")

    @field_validator("whisper_model")
    @classmethod
    def validate_whisper_model(cls, v: str) -> str:
        """验证 Whisper 模型"""
        valid_models = ["tiny", "base", "small", "medium", "large"]
        if v not in valid_models:
            raise ValueError(f"Invalid Whisper model: {v}. Must be one of {valid_models}")
        return v


class AgentEngineConfig(ServiceConfig):
    """Agent Engine 特定配置"""

    service_name: str = Field(default="agent-engine", description="服务名称")
    port: int = Field(default=8003, ge=1024, le=65535, description="监听端口")

    # Agent Engine 特定配置
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM 配置")
    milvus: MilvusConfig = Field(default_factory=MilvusConfig, description="Milvus 配置")
    max_steps: int = Field(default=10, ge=1, le=50, description="最大执行步骤")
    memory_window: int = Field(default=10, ge=1, le=100, description="记忆窗口大小")


# 配置工厂函数
def load_service_config(config_class: type = ServiceConfig) -> BaseSettings:
    """
    加载服务配置

    Args:
        config_class: 配置类（默认为 ServiceConfig）

    Returns:
        配置实例

    Raises:
        ValidationError: 如果配置验证失败
    """
    try:
        config = config_class()
        return config
    except Exception as e:
        # 打印详细错误信息
        import sys
        print(f"❌ Configuration validation failed: {e}", file=sys.stderr)
        raise


# 使用示例
if __name__ == "__main__":
    # 测试配置加载
    try:
        config = load_service_config(ServiceConfig)
        print("✅ Configuration loaded successfully")
        print(f"Service: {config.service_name}")
        print(f"Environment: {config.environment}")
        print(f"Port: {config.port}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
