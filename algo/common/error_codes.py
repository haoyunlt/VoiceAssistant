"""
统一错误码规范

错误码范围：
- 10000-19999: 通用错误（HTTP 4xx）
- 20000-29999: 业务逻辑错误
- 30000-39999: 数据访问错误
- 40000-49999: 外部服务错误
- 50000-59999: 系统级错误（HTTP 5xx）
"""

from enum import IntEnum
from typing import Any


class ErrorCategory(IntEnum):
    """错误分类"""

    GENERAL = 10000  # 通用错误
    BUSINESS = 20000  # 业务错误
    DATA = 30000  # 数据错误
    SERVICE = 40000  # 服务错误
    SYSTEM = 50000  # 系统错误


# ==================== 通用错误 (10000-19999) ====================


class GeneralError(IntEnum):
    """通用错误码"""

    # 基础错误 (10000-10099)
    BAD_REQUEST = 10000
    UNAUTHORIZED = 10001
    FORBIDDEN = 10002
    NOT_FOUND = 10003
    CONFLICT = 10004
    VALIDATION_FAILED = 10005
    TOO_MANY_REQUESTS = 10006
    REQUEST_TIMEOUT = 10007

    # 参数错误 (10100-10199)
    INVALID_PARAMETER = 10100
    MISSING_PARAMETER = 10101
    PARAMETER_OUT_OF_RANGE = 10102
    INVALID_FORMAT = 10103


# ==================== 业务逻辑错误 (20000-29999) ====================


class BusinessError(IntEnum):
    """业务逻辑错误码"""

    # 任务相关 (20000-20099)
    TASK_NOT_FOUND = 20000
    TASK_ALREADY_EXISTS = 20001
    TASK_EXECUTION_FAILED = 20002
    TASK_TIMEOUT = 20003
    TASK_CANCELLED = 20004
    INVALID_TASK_TYPE = 20005
    TASK_QUEUE_FULL = 20006

    # Agent 相关 (20100-20199)
    AGENT_NOT_FOUND = 20100
    AGENT_INIT_FAILED = 20101
    TOOL_NOT_FOUND = 20102
    TOOL_EXECUTION_FAILED = 20103
    MEMORY_NOT_FOUND = 20104
    INVALID_AGENT_MODE = 20105

    # LLM 相关 (20200-20299)
    LLM_TIMEOUT = 20200
    LLM_RATE_LIMITED = 20201
    LLM_QUOTA_EXCEEDED = 20202
    LLM_INVALID_RESPONSE = 20203
    MODEL_NOT_SUPPORTED = 20204
    TOKEN_LIMIT_EXCEEDED = 20205

    # RAG 相关 (20300-20399)
    RETRIEVAL_FAILED = 20300
    EMBEDDING_FAILED = 20301
    RERANK_FAILED = 20302
    INDEX_NOT_FOUND = 20303
    DOCUMENT_NOT_FOUND = 20304

    # 语音相关 (20400-20499)
    ASR_FAILED = 20400
    TTS_FAILED = 20401
    VAD_FAILED = 20402
    AUDIO_FORMAT_INVALID = 20403


# ==================== 数据访问错误 (30000-39999) ====================


class DataError(IntEnum):
    """数据访问错误码"""

    # 数据库错误 (30000-30099)
    DATABASE_ERROR = 30000
    RECORD_NOT_FOUND = 30001
    DUPLICATE_RECORD = 30002
    CONNECTION_FAILED = 30003
    QUERY_TIMEOUT = 30004

    # 缓存错误 (30100-30199)
    CACHE_ERROR = 30100
    CACHE_MISS = 30101
    CACHE_EXPIRED = 30102

    # 向量数据库错误 (30200-30299)
    MILVUS_ERROR = 30200
    COLLECTION_NOT_FOUND = 30201
    VECTOR_SEARCH_FAILED = 30202


# ==================== 外部服务错误 (40000-49999) ====================


class ServiceError(IntEnum):
    """外部服务错误码"""

    # 服务调用错误 (40000-40099)
    SERVICE_CALL_FAILED = 40000
    SERVICE_UNAVAILABLE = 40001
    SERVICE_TIMEOUT = 40002
    CIRCUIT_BREAKER_OPEN = 40003

    # 第三方服务 (40100-40199)
    OPENAI_ERROR = 40100
    ANTHROPIC_ERROR = 40101
    MINIO_ERROR = 40102
    NACOS_ERROR = 40103
    REDIS_ERROR = 40104


# ==================== 系统错误 (50000-59999) ====================


class SystemError(IntEnum):
    """系统级错误码"""

    # 内部错误 (50000-50099)
    INTERNAL_SERVER_ERROR = 50000
    UNKNOWN_ERROR = 50001
    NOT_IMPLEMENTED = 50002
    CONFIG_ERROR = 50003

    # 资源错误 (50100-50199)
    OUT_OF_MEMORY = 50100
    DISK_FULL = 50101
    RESOURCE_EXHAUSTED = 50102


# ==================== 异常类定义 ====================


class BaseAppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        code: int,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        """
        初始化异常

        Args:
            code: 错误码
            message: 错误消息
            details: 详细信息
            cause: 原始异常
        """
        self.code = code
        self.message = message
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "code": self.code,
            "message": self.message,
        }

        if self.details:
            result["details"] = self.details

        if self.cause:
            result["cause"] = str(self.cause)

        return result

    def __str__(self) -> str:
        """字符串表示"""
        return f"[{self.code}] {self.message}"


class GeneralException(BaseAppException):
    """通用异常（4xx）"""

    def __init__(
        self,
        code: GeneralError,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        message = message or code.name.replace("_", " ").title()
        super().__init__(code.value, message, details, cause)


class BusinessException(BaseAppException):
    """业务异常"""

    def __init__(
        self,
        code: BusinessError,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        message = message or code.name.replace("_", " ").title()
        super().__init__(code.value, message, details, cause)


class DataException(BaseAppException):
    """数据访问异常（5xx）"""

    def __init__(
        self,
        code: DataError,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        message = message or code.name.replace("_", " ").title()
        super().__init__(code.value, message, details, cause)


class ServiceException(BaseAppException):
    """外部服务异常（5xx）"""

    def __init__(
        self,
        code: ServiceError,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        message = message or code.name.replace("_", " ").title()
        super().__init__(code.value, message, details, cause)


class SystemException(BaseAppException):
    """系统异常（5xx）"""

    def __init__(
        self,
        code: SystemError,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        message = message or code.name.replace("_", " ").title()
        super().__init__(code.value, message, details, cause)


# ==================== 便捷函数 ====================


def get_http_status(code: int) -> int:
    """
    根据错误码获取 HTTP 状态码

    Args:
        code: 错误码

    Returns:
        HTTP 状态码
    """
    if 10000 <= code < 20000:
        # 通用错误 -> 4xx
        if code == GeneralError.UNAUTHORIZED:
            return 401
        elif code == GeneralError.FORBIDDEN:
            return 403
        elif code == GeneralError.NOT_FOUND:
            return 404
        elif code == GeneralError.CONFLICT:
            return 409
        elif code == GeneralError.TOO_MANY_REQUESTS:
            return 429
        else:
            return 400
    elif 20000 <= code < 30000:
        # 业务错误 -> 400
        return 400
    elif 30000 <= code < 40000:
        # 数据错误 -> 500
        return 500
    elif 40000 <= code < 50000:
        # 服务错误 -> 503
        return 503
    elif 50000 <= code < 60000:
        # 系统错误 -> 500
        return 500
    else:
        return 500


def is_retryable(code: int) -> bool:
    """
    判断错误是否可重试

    Args:
        code: 错误码

    Returns:
        是否可重试
    """
    retryable_codes = {
        GeneralError.REQUEST_TIMEOUT,
        GeneralError.TOO_MANY_REQUESTS,
        BusinessError.LLM_TIMEOUT,
        BusinessError.LLM_RATE_LIMITED,
        DataError.QUERY_TIMEOUT,
        ServiceError.SERVICE_TIMEOUT,
        ServiceError.SERVICE_UNAVAILABLE,
    }

    return code in {c.value for c in retryable_codes}


def get_error_category(code: int) -> str:
    """
    获取错误分类

    Args:
        code: 错误码

    Returns:
        错误分类名称
    """
    if 10000 <= code < 20000:
        return "GENERAL"
    elif 20000 <= code < 30000:
        return "BUSINESS"
    elif 30000 <= code < 40000:
        return "DATA"
    elif 40000 <= code < 50000:
        return "SERVICE"
    elif 50000 <= code < 60000:
        return "SYSTEM"
    else:
        return "UNKNOWN"


# ==================== 预定义异常实例 ====================


# 通用异常
def BadRequestError(msg="Bad request", **kw):
    return GeneralException(GeneralError.BAD_REQUEST, msg, **kw)


def UnauthorizedError(msg="Unauthorized", **kw):
    return GeneralException(GeneralError.UNAUTHORIZED, msg, **kw)


def ForbiddenError(msg="Forbidden", **kw):
    return GeneralException(GeneralError.FORBIDDEN, msg, **kw)


def NotFoundError(msg="Not found", **kw):
    return GeneralException(GeneralError.NOT_FOUND, msg, **kw)


# 业务异常
def TaskNotFoundError(msg="Task not found", **kw):
    return BusinessException(BusinessError.TASK_NOT_FOUND, msg, **kw)


def ToolNotFoundError(msg="Tool not found", **kw):
    return BusinessException(BusinessError.TOOL_NOT_FOUND, msg, **kw)


def LLMTimeoutError(msg="LLM request timeout", **kw):
    return BusinessException(BusinessError.LLM_TIMEOUT, msg, **kw)


# 数据异常
def RecordNotFoundError(msg="Record not found", **kw):
    return DataException(DataError.RECORD_NOT_FOUND, msg, **kw)


def DatabaseError(msg="Database error", **kw):
    return DataException(DataError.DATABASE_ERROR, msg, **kw)


# 服务异常
def ServiceUnavailableError(msg="Service unavailable", **kw):
    return ServiceException(ServiceError.SERVICE_UNAVAILABLE, msg, **kw)
