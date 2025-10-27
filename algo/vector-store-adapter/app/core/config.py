"""配置管理"""

import os
from typing import Any, Dict


class Config:
    """配置类"""

    # 服务配置
    SERVICE_NAME = "vector-store-adapter"
    VERSION = "1.0.0"

    # Milvus 配置
    MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
    MILVUS_PORT = int(os.getenv("MILVUS_PORT", "19530"))
    MILVUS_USER = os.getenv("MILVUS_USER", "")
    MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")

    # PostgreSQL (pgvector) 配置
    PGVECTOR_HOST = os.getenv("PGVECTOR_HOST", "localhost")
    PGVECTOR_PORT = int(os.getenv("PGVECTOR_PORT", "5432"))
    PGVECTOR_DATABASE = os.getenv("PGVECTOR_DATABASE", "voiceassistant")
    PGVECTOR_USER = os.getenv("PGVECTOR_USER", "postgres")
    PGVECTOR_PASSWORD = os.getenv("PGVECTOR_PASSWORD", "")

    # 默认后端
    DEFAULT_BACKEND = os.getenv("DEFAULT_BACKEND", "milvus")

    # 向量维度
    VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "1024"))

    # Redis 缓存（可选）
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    @classmethod
    def get_backend_config(cls, backend: str) -> Dict[str, Any]:
        """获取特定后端的配置"""
        if backend == "milvus":
            return {
                "host": cls.MILVUS_HOST,
                "port": cls.MILVUS_PORT,
                "user": cls.MILVUS_USER,
                "password": cls.MILVUS_PASSWORD,
            }
        elif backend == "pgvector":
            return {
                "host": cls.PGVECTOR_HOST,
                "port": cls.PGVECTOR_PORT,
                "database": cls.PGVECTOR_DATABASE,
                "user": cls.PGVECTOR_USER,
                "password": cls.PGVECTOR_PASSWORD,
            }
        else:
            raise ValueError(f"Unknown backend: {backend}")


config = Config()
