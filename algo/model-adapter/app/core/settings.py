"""配置管理."""


from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProviderConfig(BaseModel):
    """提供商配置."""

    api_key: str
    base_url: str | None = None
    timeout: float = 60.0
    max_retries: int = 3
    enabled: bool = True


class Settings(BaseSettings):
    """应用配置."""

    # 应用配置
    app_name: str = "Model Adapter"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # 服务配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8005, env="PORT")
    workers: int = Field(default=1, env="WORKERS")

    # CORS配置
    cors_origins: list[str] = Field(default=["*"], env="CORS_ORIGINS")
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # OpenAI配置
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, env="OPENAI_BASE_URL")
    openai_timeout: float = Field(default=60.0, env="OPENAI_TIMEOUT")
    openai_enabled: bool = Field(default=True, env="OPENAI_ENABLED")

    # Claude配置
    anthropic_api_key: str | None = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_timeout: float = Field(default=60.0, env="ANTHROPIC_TIMEOUT")
    anthropic_enabled: bool = Field(default=True, env="ANTHROPIC_ENABLED")

    # 智谱AI配置
    zhipu_api_key: str | None = Field(default=None, env="ZHIPU_API_KEY")
    zhipu_timeout: float = Field(default=60.0, env="ZHIPU_TIMEOUT")
    zhipu_enabled: bool = Field(default=True, env="ZHIPU_ENABLED")

    # 通义千问配置
    dashscope_api_key: str | None = Field(default=None, env="DASHSCOPE_API_KEY")
    dashscope_timeout: float = Field(default=60.0, env="DASHSCOPE_TIMEOUT")
    dashscope_enabled: bool = Field(default=True, env="DASHSCOPE_ENABLED")

    # 百度文心配置
    baidu_api_key: str | None = Field(default=None, env="BAIDU_API_KEY")
    baidu_secret_key: str | None = Field(default=None, env="BAIDU_SECRET_KEY")
    baidu_timeout: float = Field(default=60.0, env="BAIDU_TIMEOUT")
    baidu_enabled: bool = Field(default=True, env="BAIDU_ENABLED")

    # 限流配置
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(
        default=60, env="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )

    # 缓存配置
    cache_enabled: bool = Field(default=False, env="CACHE_ENABLED")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")
    redis_url: str | None = Field(default=None, env="REDIS_URL")

    # 监控配置
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    enable_tracing: bool = Field(default=False, env="ENABLE_TRACING")
    otel_endpoint: str | None = Field(default=None, env="OTEL_ENDPOINT")

    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
    )

    # 重试配置
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    retry_backoff_factor: float = Field(default=2.0, env="RETRY_BACKOFF_FACTOR")

    class Config:
        """Pydantic配置."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_provider_config(self, provider: str) -> ProviderConfig | None:
        """
        获取提供商配置.

        Args:
            provider: 提供商名称

        Returns:
            提供商配置，如果未配置则返回None
        """
        provider_configs: dict[str, ProviderConfig | None] = {
            "openai": (
                ProviderConfig(
                    api_key=self.openai_api_key,
                    base_url=self.openai_base_url,
                    timeout=self.openai_timeout,
                    enabled=self.openai_enabled,
                )
                if self.openai_api_key
                else None
            ),
            "claude": (
                ProviderConfig(
                    api_key=self.anthropic_api_key,
                    timeout=self.anthropic_timeout,
                    enabled=self.anthropic_enabled,
                )
                if self.anthropic_api_key
                else None
            ),
            "zhipu": (
                ProviderConfig(
                    api_key=self.zhipu_api_key,
                    timeout=self.zhipu_timeout,
                    enabled=self.zhipu_enabled,
                )
                if self.zhipu_api_key
                else None
            ),
            "qwen": (
                ProviderConfig(
                    api_key=self.dashscope_api_key,
                    timeout=self.dashscope_timeout,
                    enabled=self.dashscope_enabled,
                )
                if self.dashscope_api_key
                else None
            ),
            "baidu": (
                ProviderConfig(
                    api_key=f"{self.baidu_api_key}:{self.baidu_secret_key}",
                    timeout=self.baidu_timeout,
                    enabled=self.baidu_enabled,
                )
                if self.baidu_api_key and self.baidu_secret_key
                else None
            ),
        }

        return provider_configs.get(provider)

    def list_enabled_providers(self) -> list[str]:
        """
        列出所有已启用的提供商.

        Returns:
            提供商名称列表
        """
        enabled_providers = []

        if self.openai_api_key and self.openai_enabled:
            enabled_providers.append("openai")
        if self.anthropic_api_key and self.anthropic_enabled:
            enabled_providers.append("claude")
        if self.zhipu_api_key and self.zhipu_enabled:
            enabled_providers.append("zhipu")
        if self.dashscope_api_key and self.dashscope_enabled:
            enabled_providers.append("qwen")
        if self.baidu_api_key and self.baidu_secret_key and self.baidu_enabled:
            enabled_providers.append("baidu")

        return enabled_providers


# 全局配置实例
settings = Settings()
