"""
Agent Engine 配置管理
"""

from typing import Optional

from pydantic import BaseSettings, Field


class AgentConfig(BaseSettings):
    """Agent Engine 配置"""

    # 服务配置
    service_name: str = Field(default="agent-engine", env="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8003, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    reload: bool = Field(default=False, env="RELOAD")

    # LLM配置
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4", env="LLM_MODEL")
    llm_api_key: Optional[str] = Field(default=None, env="LLM_API_KEY")
    llm_api_base: Optional[str] = Field(default=None, env="LLM_API_BASE")
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    llm_timeout: int = Field(default=30, env="LLM_TIMEOUT")

    # Agent配置
    default_mode: str = Field(default="react", env="AGENT_DEFAULT_MODE")
    max_steps: int = Field(default=10, env="AGENT_MAX_STEPS")
    max_iterations: int = Field(default=3, env="AGENT_MAX_ITERATIONS")
    enable_reflexion: bool = Field(default=False, env="AGENT_ENABLE_REFLEXION")

    # 工具配置
    tool_timeout: int = Field(default=10, env="TOOL_TIMEOUT")
    enable_all_tools: bool = Field(default=True, env="ENABLE_ALL_TOOLS")

    # 记忆配置
    memory_enabled: bool = Field(default=True, env="MEMORY_ENABLED")
    memory_max_tokens: int = Field(default=2000, env="MEMORY_MAX_TOKENS")
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 性能配置
    timeout: int = Field(default=60, env="AGENT_TIMEOUT")
    max_retries: int = Field(default=3, env="AGENT_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, env="AGENT_RETRY_DELAY")

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
_config: Optional[AgentConfig] = None


def get_config() -> AgentConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = AgentConfig()
    return _config


def reload_config() -> AgentConfig:
    """重新加载配置"""
    global _config
    _config = AgentConfig()
    return _config
