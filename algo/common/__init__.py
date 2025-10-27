"""
algo/common - 所有AI服务的公共模块

这个包包含：
- 统一LLM客户端 (llm_client.py)
- 统一向量存储客户端 (vector_store_client.py)
- 统一配置基类 (config_base.py)
- 统一结构化日志 (structured_logging.py) - 支持JSON格式、Trace ID集成
- 统一认证中间件 (auth_middleware.py)
- 统一弹性机制 (resilience.py) - 熔断器、重试
- 统一追踪 (telemetry.py) - OpenTelemetry集成
- 成本追踪 (cost_tracking.py)
- Nacos配置支持 (nacos_config.py)

使用示例：
    from algo.common.llm_client import UnifiedLLMClient
    from algo.common.vector_store_client import VectorStoreClient
    from algo.common.config_base import ServiceConfigBase, LLMConfigMixin
    from algo.common.structured_logging import setup_logging
"""

__version__ = "1.0.0"

# 导出公共类和函数
# 导出中间件和工具
from .auth_middleware import AuthMiddleware, RequireRole, optional_auth, require_auth
from .config_base import (
    LLMConfigMixin,
    RetrievalConfigMixin,
    ServiceConfigBase,
    VectorStoreConfigMixin,
)
from .cost_tracking import (
    cost_tracking_middleware,
    get_cost_summary,
    track_embedding_usage,
    track_llm_usage,
)
from .llm_client import UnifiedLLMClient
from .resilience import CircuitBreaker, with_retry, with_timeout
from .structured_logging import get_request_id, logging_middleware, set_request_id, setup_logging
from .telemetry import get_tracer, init_tracing, traced
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
    "set_request_id",
    "get_request_id",
    "logging_middleware",
    # 认证
    "AuthMiddleware",
    "RequireRole",
    "require_auth",
    "optional_auth",
    # 弹性
    "CircuitBreaker",
    "with_retry",
    "with_timeout",
    # 追踪
    "init_tracing",
    "traced",
    "get_tracer",
    # 成本追踪
    "track_llm_usage",
    "track_embedding_usage",
    "get_cost_summary",
    "cost_tracking_middleware",
]
