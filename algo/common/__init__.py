"""
algo/common - 所有AI服务的公共模块

这个包包含：
- 统一LLM客户端 (llm_client.py)
- 统一向量存储客户端 (vector_store_client.py)
- 统一配置基类 (config_base.py)
- 统一日志配置 (logging_config.py)
- Nacos配置支持 (nacos_config.py)

使用示例：
    from algo.common.llm_client import UnifiedLLMClient
    from algo.common.vector_store_client import VectorStoreClient
    from algo.common.config_base import ServiceConfigBase, LLMConfigMixin
    from algo.common.logging_config import setup_logging, get_logger
"""

__version__ = "1.0.0"

# 导出公共类和函数
from .config_base import (
    LLMConfigMixin,
    RetrievalConfigMixin,
    ServiceConfigBase,
    VectorStoreConfigMixin,
)
from .llm_client import UnifiedLLMClient
from .logging_config import get_logger, setup_logging, silence_noisy_loggers
from .vector_store_client import VectorStoreClient

__all__ = [
    # 配置
    "ServiceConfigBase",
    "LLMConfigMixin",
    "VectorStoreConfigMixin",
    "RetrievalConfigMixin",
    # 客户端
    "UnifiedLLMClient",
    "VectorStoreClient",
    # 日志
    "setup_logging",
    "get_logger",
    "silence_noisy_loggers",
]
