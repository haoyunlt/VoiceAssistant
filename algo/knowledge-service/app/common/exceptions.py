"""
Custom Exceptions - 自定义异常类

定义知识服务的异常层次结构
"""


class KnowledgeServiceError(Exception):
    """知识服务基础异常"""

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码
            details: 错误详情
        """
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}


# ============= LLM相关异常 =============


class LLMError(KnowledgeServiceError):
    """LLM调用异常基类"""

    pass


class LLMExtractionError(LLMError):
    """LLM实体提取失败"""

    def __init__(self, message: str, model: str | None = None, **kwargs):
        super().__init__(message, code="LLM_EXTRACTION_ERROR", **kwargs)
        self.model = model


class LLMSummarizationError(LLMError):
    """LLM摘要生成失败"""

    def __init__(self, message: str, model: str | None = None, **kwargs):
        super().__init__(message, code="LLM_SUMMARIZATION_ERROR", **kwargs)
        self.model = model


class LLMQuotaExceededError(LLMError):
    """LLM配额超限"""

    def __init__(self, message: str, model: str | None = None, **kwargs):
        super().__init__(message, code="LLM_QUOTA_EXCEEDED", **kwargs)
        self.model = model


class LLMTimeoutError(LLMError):
    """LLM请求超时"""

    def __init__(self, message: str, timeout: float | None = None, **kwargs):
        super().__init__(message, code="LLM_TIMEOUT", **kwargs)
        self.timeout = timeout


# ============= 图数据库相关异常 =============


class GraphDBError(KnowledgeServiceError):
    """图数据库异常基类"""

    pass


class Neo4jConnectionError(GraphDBError):
    """Neo4j连接失败"""

    def __init__(self, message: str, uri: str | None = None, **kwargs):
        super().__init__(message, code="NEO4J_CONNECTION_ERROR", **kwargs)
        self.uri = uri


class Neo4jQueryError(GraphDBError):
    """Neo4j查询失败"""

    def __init__(self, message: str, query: str | None = None, **kwargs):
        super().__init__(message, code="NEO4J_QUERY_ERROR", **kwargs)
        self.query = query


# ============= 检索相关异常 =============


class RetrievalError(KnowledgeServiceError):
    """检索异常基类"""

    pass


class GraphRetrievalError(RetrievalError):
    """图谱检索失败"""

    def __init__(self, message: str, query: str | None = None, **kwargs):
        super().__init__(message, code="GRAPH_RETRIEVAL_ERROR", **kwargs)
        self.query = query


class VectorRetrievalError(RetrievalError):
    """向量检索失败"""

    def __init__(self, message: str, query: str | None = None, **kwargs):
        super().__init__(message, code="VECTOR_RETRIEVAL_ERROR", **kwargs)
        self.query = query


class BM25RetrievalError(RetrievalError):
    """BM25检索失败"""

    def __init__(self, message: str, query: str | None = None, **kwargs):
        super().__init__(message, code="BM25_RETRIEVAL_ERROR", **kwargs)
        self.query = query


# ============= GraphRAG相关异常 =============


class GraphRAGError(KnowledgeServiceError):
    """GraphRAG异常基类"""

    pass


class IndexBuildError(GraphRAGError):
    """索引构建失败"""

    def __init__(self, message: str, document_id: str | None = None, **kwargs):
        super().__init__(message, code="INDEX_BUILD_ERROR", **kwargs)
        self.document_id = document_id


class CommunityDetectionError(GraphRAGError):
    """社区检测失败"""

    def __init__(self, message: str, algorithm: str | None = None, **kwargs):
        super().__init__(message, code="COMMUNITY_DETECTION_ERROR", **kwargs)
        self.algorithm = algorithm


class IncrementalUpdateError(GraphRAGError):
    """增量更新失败"""

    def __init__(self, message: str, document_id: str | None = None, **kwargs):
        super().__init__(message, code="INCREMENTAL_UPDATE_ERROR", **kwargs)
        self.document_id = document_id


# ============= 实体链接相关异常 =============


class EntityLinkingError(KnowledgeServiceError):
    """实体链接异常"""

    def __init__(self, message: str, entity_id: str | None = None, **kwargs):
        super().__init__(message, code="ENTITY_LINKING_ERROR", **kwargs)
        self.entity_id = entity_id


class EntityMergeError(KnowledgeServiceError):
    """实体合并异常"""

    def __init__(
        self,
        message: str,
        source_id: str | None = None,
        target_id: str | None = None,
        **kwargs,
    ):
        super().__init__(message, code="ENTITY_MERGE_ERROR", **kwargs)
        self.source_id = source_id
        self.target_id = target_id


# ============= 缓存相关异常 =============


class CacheError(KnowledgeServiceError):
    """缓存异常基类"""

    pass


class CacheConnectionError(CacheError):
    """缓存连接失败"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="CACHE_CONNECTION_ERROR", **kwargs)


class CacheOperationError(CacheError):
    """缓存操作失败"""

    def __init__(self, message: str, operation: str | None = None, **kwargs):
        super().__init__(message, code="CACHE_OPERATION_ERROR", **kwargs)
        self.operation = operation


# ============= 验证相关异常 =============


class ValidationError(KnowledgeServiceError):
    """数据验证异常"""

    def __init__(self, message: str, field: str | None = None, **kwargs):
        super().__init__(message, code="VALIDATION_ERROR", **kwargs)
        self.field = field


class ResourceNotFoundError(KnowledgeServiceError):
    """资源未找到"""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        **kwargs,
    ):
        super().__init__(message, code="RESOURCE_NOT_FOUND", **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


# ============= 配置相关异常 =============


class ConfigurationError(KnowledgeServiceError):
    """配置错误"""

    def __init__(self, message: str, config_key: str | None = None, **kwargs):
        super().__init__(message, code="CONFIGURATION_ERROR", **kwargs)
        self.config_key = config_key
