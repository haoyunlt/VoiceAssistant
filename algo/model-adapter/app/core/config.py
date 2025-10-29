"""配置管理"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    SERVICE_NAME: str = "model-adapter"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8005, env="PORT")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS配置
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # OpenAI配置
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OPENAI_API_BASE: str = Field(
        default="https://api.openai.com/v1", env="OPENAI_API_BASE"
    )
    OPENAI_ORG_ID: str = Field(default="", env="OPENAI_ORG_ID")

    # Azure OpenAI配置
    AZURE_OPENAI_API_KEY: str = Field(default="", env="AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: str = Field(default="", env="AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION: str = Field(
        default="2024-02-01", env="AZURE_OPENAI_API_VERSION"
    )

    # Anthropic配置
    ANTHROPIC_API_KEY: str = Field(default="", env="ANTHROPIC_API_KEY")
    ANTHROPIC_API_BASE: str = Field(
        default="https://api.anthropic.com", env="ANTHROPIC_API_BASE"
    )

    # 智谱AI配置
    ZHIPU_API_KEY: str = Field(default="", env="ZHIPU_API_KEY")
    ZHIPU_API_BASE: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4", env="ZHIPU_API_BASE"
    )

    # 通义千问配置
    QWEN_API_KEY: str = Field(default="", env="QWEN_API_KEY")
    QWEN_API_BASE: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1", env="QWEN_API_BASE"
    )

    # 百度文心配置
    BAIDU_API_KEY: str = Field(default="", env="BAIDU_API_KEY")
    BAIDU_SECRET_KEY: str = Field(default="", env="BAIDU_SECRET_KEY")
    BAIDU_API_BASE: str = Field(
        default="https://aip.baidubce.com", env="BAIDU_API_BASE"
    )

    # 模型映射配置
    MODEL_MAPPINGS: dict[str, str] = Field(
        default={
            "gpt-4": "openai/gpt-4",
            "gpt-3.5-turbo": "openai/gpt-3.5-turbo",
            "claude-3-opus": "anthropic/claude-3-opus-20240229",
            "claude-3-sonnet": "anthropic/claude-3-sonnet-20240229",
            "glm-4": "zhipu/glm-4",
            "qwen-max": "qwen/qwen-max",
            "ernie-bot": "baidu/ERNIE-Bot-4",
        }
    )

    # 超时配置
    REQUEST_TIMEOUT: int = Field(default=60, env="REQUEST_TIMEOUT")

    # 重试配置
    MAX_RETRIES: int = Field(default=3, env="MAX_RETRIES")
    RETRY_DELAY: float = Field(default=1.0, env="RETRY_DELAY")

    # Redis配置（可选，用于缓存）
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 数据库配置（如需持久化）
    DATABASE_URL: str = Field(
        default="postgresql://voiceassistant:voiceassistant_dev@localhost:5432/voiceassistant",
        env="DATABASE_URL",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
