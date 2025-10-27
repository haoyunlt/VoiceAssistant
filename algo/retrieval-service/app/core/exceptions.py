"""
自定义异常类
"""


class RetrievalServiceError(Exception):
    """检索服务基础异常"""

    pass


class VectorStoreError(RetrievalServiceError):
    """向量存储异常"""

    pass


class BM25Error(RetrievalServiceError):
    """BM25检索异常"""

    pass


class GraphStoreError(RetrievalServiceError):
    """图数据库异常"""

    pass


class CacheError(RetrievalServiceError):
    """缓存异常"""

    pass


class RerankError(RetrievalServiceError):
    """重排序异常"""

    pass


class TimeoutError(RetrievalServiceError):
    """超时异常"""

    pass


class CircuitBreakerOpenError(RetrievalServiceError):
    """熔断器开启异常"""

    pass
