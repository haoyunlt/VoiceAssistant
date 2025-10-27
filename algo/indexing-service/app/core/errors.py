"""自定义错误类型和错误处理"""
from enum import Enum
from typing import Optional


class ErrorType(Enum):
    """错误类型枚举"""
    # 可重试错误
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVICE_UNAVAILABLE = "service_unavailable"

    # 不可重试错误
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    INVALID_FORMAT = "invalid_format"
    FILE_TOO_LARGE = "file_too_large"

    # 系统错误
    INTERNAL_ERROR = "internal_error"
    STORAGE_ERROR = "storage_error"
    EMBEDDING_ERROR = "embedding_error"
    VECTOR_STORE_ERROR = "vector_store_error"
    GRAPH_ERROR = "graph_error"


class IndexingError(Exception):
    """索引服务基础异常"""

    def __init__(
        self,
        message: str,
        error_type: ErrorType,
        retryable: bool = False,
        tenant_id: Optional[str] = None,
        document_id: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.retryable = retryable
        self.tenant_id = tenant_id
        self.document_id = document_id
        self.details = details or {}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "error": self.message,
            "error_type": self.error_type.value,
            "retryable": self.retryable,
            "tenant_id": self.tenant_id,
            "document_id": self.document_id,
            "details": self.details,
        }


class NetworkError(IndexingError):
    """网络错误（可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.NETWORK_ERROR,
            retryable=True,
            **kwargs
        )


class TimeoutError(IndexingError):
    """超时错误（可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.TIMEOUT_ERROR,
            retryable=True,
            **kwargs
        )


class StorageError(IndexingError):
    """存储错误（可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.STORAGE_ERROR,
            retryable=True,
            **kwargs
        )


class InvalidInputError(IndexingError):
    """无效输入错误（不可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.INVALID_INPUT,
            retryable=False,
            **kwargs
        )


class DocumentNotFoundError(IndexingError):
    """文档未找到错误（不可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.NOT_FOUND,
            retryable=False,
            **kwargs
        )


class FileTooLargeError(IndexingError):
    """文件过大错误（不可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.FILE_TOO_LARGE,
            retryable=False,
            **kwargs
        )


class EmbeddingError(IndexingError):
    """向量化错误（部分可重试）"""
    def __init__(self, message: str, retryable: bool = True, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.EMBEDDING_ERROR,
            retryable=retryable,
            **kwargs
        )


class VectorStoreError(IndexingError):
    """向量存储错误（可重试）"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_type=ErrorType.VECTOR_STORE_ERROR,
            retryable=True,
            **kwargs
        )


def is_retryable_error(error: Exception) -> bool:
    """判断错误是否可重试"""
    if isinstance(error, IndexingError):
        return error.retryable

    # 判断常见的可重试错误
    error_name = type(error).__name__
    retryable_errors = {
        "ConnectionError",
        "TimeoutError",
        "ReadTimeout",
        "ConnectTimeout",
        "HTTPError",  # 需要根据状态码判断
        "ServiceUnavailable",
    }

    return error_name in retryable_errors


def get_error_type(error: Exception) -> ErrorType:
    """获取错误类型"""
    if isinstance(error, IndexingError):
        return error.error_type

    # 根据异常类型推断错误类型
    error_name = type(error).__name__

    if "Timeout" in error_name:
        return ErrorType.TIMEOUT_ERROR
    elif "Connection" in error_name:
        return ErrorType.NETWORK_ERROR
    elif "NotFound" in error_name:
        return ErrorType.NOT_FOUND
    elif "Permission" in error_name:
        return ErrorType.PERMISSION_DENIED
    else:
        return ErrorType.INTERNAL_ERROR
