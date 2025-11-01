"""配置管理"""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    SERVICE_NAME: str = "indexing-service"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8004, env="PORT")

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    # CORS配置
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        env="CORS_ORIGINS",
    )

    # Embedding模型配置
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-m3", env="EMBEDDING_MODEL")
    EMBEDDING_DIMENSION: int = Field(default=1024, env="EMBEDDING_DIMENSION")
    EMBEDDING_BATCH_SIZE: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")

    # OpenAI API配置（备选）
    OPENAI_API_KEY: str = Field(default="", env="OPENAI_API_KEY")
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1", env="OPENAI_API_BASE")

    # 文档处理配置
    MAX_CHUNK_SIZE: int = Field(default=512, env="MAX_CHUNK_SIZE")
    CHUNK_OVERLAP: int = Field(default=50, env="CHUNK_OVERLAP")
    SUPPORTED_FORMATS: list[str] = Field(
        default=["pdf", "docx", "txt", "md", "html"],
        env="SUPPORTED_FORMATS",
    )

    # Milvus配置
    MILVUS_HOST: str = Field(default="localhost", env="MILVUS_HOST")
    MILVUS_PORT: int = Field(default=19530, env="MILVUS_PORT")
    MILVUS_COLLECTION: str = Field(default="documents", env="MILVUS_COLLECTION")

    # Neo4j配置
    NEO4J_URI: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(default="password", env="NEO4J_PASSWORD")

    # MinIO/S3配置
    MINIO_ENDPOINT: str = Field(default="localhost:9000", env="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", env="MINIO_SECRET_KEY")
    MINIO_BUCKET: str = Field(default="documents", env="MINIO_BUCKET")
    MINIO_SECURE: bool = Field(default=False, env="MINIO_SECURE")

    # Redis配置（可选，用于缓存）
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql://voiceassistant:voiceassistant_dev@localhost:5432/voiceassistant",
        env="DATABASE_URL",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
