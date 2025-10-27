"""统一异常定义."""

from typing import Any


class ModelAdapterError(Exception):
    """模型适配器基础异常."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """
        初始化异常.

        Args:
            message: 错误消息
            provider: 提供商名称
            error_code: 错误代码
            details: 详细信息
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "provider": self.provider,
            "error_code": self.error_code,
            "details": self.details,
        }


class ProviderNotFoundError(ModelAdapterError):
    """提供商不存在."""

    def __init__(self, provider: str):
        """初始化."""
        super().__init__(
            message=f"Provider '{provider}' not found or not configured",
            provider=provider,
            error_code="PROVIDER_NOT_FOUND",
        )


class ProviderNotAvailableError(ModelAdapterError):
    """提供商不可用."""

    def __init__(self, provider: str, reason: str | None = None):
        """初始化."""
        message = f"Provider '{provider}' is not available"
        if reason:
            message += f": {reason}"
        super().__init__(
            message=message,
            provider=provider,
            error_code="PROVIDER_NOT_AVAILABLE",
            details={"reason": reason},
        )


class ProviderAPIError(ModelAdapterError):
    """提供商API调用错误."""

    def __init__(
        self,
        provider: str,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        """初始化."""
        super().__init__(
            message=f"API error from {provider}: {message}",
            provider=provider,
            error_code="PROVIDER_API_ERROR",
            details={
                "status_code": status_code,
                "response_body": response_body,
            },
        )
        self.status_code = status_code
        self.response_body = response_body


class RequestValidationError(ModelAdapterError):
    """请求验证错误."""

    def __init__(self, message: str, field: str | None = None):
        """初始化."""
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field},
        )
        self.field = field


class RateLimitError(ModelAdapterError):
    """限流错误."""

    def __init__(
        self,
        provider: str,
        retry_after: int | None = None,
    ):
        """初始化."""
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(
            message=message,
            provider=provider,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
        )
        self.retry_after = retry_after


class RequestTimeoutError(ModelAdapterError):
    """请求超时错误."""

    def __init__(self, provider: str, timeout: float):
        """初始化."""
        super().__init__(
            message=f"Request to {provider} timed out after {timeout}s",
            provider=provider,
            error_code="TIMEOUT",
            details={"timeout": timeout},
        )
        self.timeout = timeout


class ModelNotFoundError(ModelAdapterError):
    """模型不存在."""

    def __init__(self, model: str, provider: str):
        """初始化."""
        super().__init__(
            message=f"Model '{model}' not found for provider '{provider}'",
            provider=provider,
            error_code="MODEL_NOT_FOUND",
            details={"model": model},
        )
        self.model = model


class InsufficientQuotaError(ModelAdapterError):
    """配额不足."""

    def __init__(self, provider: str):
        """初始化."""
        super().__init__(
            message=f"Insufficient quota for {provider}",
            provider=provider,
            error_code="INSUFFICIENT_QUOTA",
        )


class ContentFilterError(ModelAdapterError):
    """内容过滤错误."""

    def __init__(self, provider: str, reason: str):
        """初始化."""
        super().__init__(
            message=f"Content filtered by {provider}: {reason}",
            provider=provider,
            error_code="CONTENT_FILTERED",
            details={"reason": reason},
        )
        self.reason = reason
