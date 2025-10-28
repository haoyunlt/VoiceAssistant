"""
统一异常体系
为所有 Python 服务提供标准化的异常处理
"""

from typing import Any, Dict, Optional


class VoiceHelperError(Exception):
    """
    基础异常类
    所有自定义异常的基类
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            code: 错误代码（用于客户端识别）
            details: 额外的错误详情
            cause: 原始异常（用于异常链）
        """
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 API 响应）"""
        result = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.cause:
            result["cause"] = str(self.cause)
        return result

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (code={self.code}, details={self.details})"
        return f"{self.message} (code={self.code})"


# ==================== 服务可用性异常 ====================


class ServiceUnavailableError(VoiceHelperError):
    """服务不可用"""

    pass


class ServiceTimeoutError(VoiceHelperError):
    """服务超时"""

    pass


class CircuitBreakerOpenError(VoiceHelperError):
    """熔断器打开"""

    pass


# ==================== 资源相关异常 ====================


class ResourceNotFoundError(VoiceHelperError):
    """资源未找到"""

    pass


class ResourceExistsError(VoiceHelperError):
    """资源已存在"""

    pass


class ResourceExhaustedError(VoiceHelperError):
    """资源耗尽（如配额、限流）"""

    pass


# ==================== 验证与认证异常 ====================


class ValidationError(VoiceHelperError):
    """输入验证错误"""

    pass


class AuthenticationError(VoiceHelperError):
    """认证失败"""

    pass


class AuthorizationError(VoiceHelperError):
    """授权失败"""

    pass


# ==================== 外部服务异常 ====================


class ExternalServiceError(VoiceHelperError):
    """外部服务错误（LLM、向量库等）"""

    pass


class LLMError(ExternalServiceError):
    """LLM 调用错误"""

    pass


class VectorStoreError(ExternalServiceError):
    """向量库错误"""

    pass


class ElasticsearchError(ExternalServiceError):
    """Elasticsearch 错误"""

    pass


# ==================== 业务逻辑异常 ====================


class BusinessLogicError(VoiceHelperError):
    """业务逻辑错误"""

    pass


class InvalidStateError(BusinessLogicError):
    """无效状态"""

    pass


class OperationNotAllowedError(BusinessLogicError):
    """操作不允许"""

    pass


# ==================== 数据异常 ====================


class DataError(VoiceHelperError):
    """数据错误"""

    pass


class DataCorruptionError(DataError):
    """数据损坏"""

    pass


class DataIntegrityError(DataError):
    """数据完整性错误"""

    pass


# ==================== 配置异常 ====================


class ConfigurationError(VoiceHelperError):
    """配置错误"""

    pass


class MissingConfigError(ConfigurationError):
    """缺少必需配置"""

    pass


class InvalidConfigError(ConfigurationError):
    """配置值无效"""

    pass


# ==================== 工具函数 ====================


def wrap_exception(
    exc: Exception, message: Optional[str] = None, error_class: type = VoiceHelperError
) -> VoiceHelperError:
    """
    包装外部异常为内部异常

    Args:
        exc: 原始异常
        message: 自定义消息（默认使用原异常消息）
        error_class: 目标异常类

    Returns:
        包装后的异常
    """
    msg = message or str(exc)
    return error_class(message=msg, cause=exc, details={"original_type": type(exc).__name__})


def handle_service_error(exc: Exception, service_name: str) -> VoiceHelperError:
    """
    处理服务调用异常，转换为标准异常

    Args:
        exc: 原始异常
        service_name: 服务名称

    Returns:
        标准化异常
    """
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        return ServiceTimeoutError(
            f"{service_name} timeout", details={"service": service_name}, cause=exc
        )
    elif isinstance(exc, httpx.ConnectError):
        return ServiceUnavailableError(
            f"{service_name} unavailable", details={"service": service_name}, cause=exc
        )
    elif isinstance(exc, httpx.HTTPStatusError):
        return ExternalServiceError(
            f"{service_name} returned error: {exc.response.status_code}",
            details={"service": service_name, "status_code": exc.response.status_code},
            cause=exc,
        )
    else:
        return wrap_exception(exc, f"{service_name} error", ExternalServiceError)


# ==================== HTTP 状态码映射 ====================


def get_http_status_code(exc: VoiceHelperError) -> int:
    """
    根据异常类型返回合适的 HTTP 状态码

    Args:
        exc: 异常实例

    Returns:
        HTTP 状态码
    """
    mapping = {
        ResourceNotFoundError: 404,
        ValidationError: 400,
        AuthenticationError: 401,
        AuthorizationError: 403,
        ResourceExistsError: 409,
        ResourceExhaustedError: 429,
        ServiceUnavailableError: 503,
        ServiceTimeoutError: 504,
        CircuitBreakerOpenError: 503,
    }

    for exc_class, status_code in mapping.items():
        if isinstance(exc, exc_class):
            return status_code

    # 默认返回 500
    return 500
