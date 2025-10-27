"""异常类单元测试."""

import pytest
from app.core.exceptions import (
    ModelAdapterError,
    ProviderAPIError,
    ProviderNotAvailableError,
    ProviderNotFoundError,
    RateLimitError,
    RequestTimeoutError,
    RequestValidationError,
)


class TestExceptions:
    """测试异常类."""

    def test_base_exception(self):
        """测试基础异常."""
        exc = ModelAdapterError(
            message="Test error",
            provider="test",
            error_code="TEST_ERROR",
            details={"key": "value"},
        )

        assert exc.message == "Test error"
        assert exc.provider == "test"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details["key"] == "value"

    def test_exception_to_dict(self):
        """测试异常转字典."""
        exc = ModelAdapterError(
            message="Test error",
            provider="test",
            error_code="TEST_ERROR",
        )

        result = exc.to_dict()

        assert result["error"] == "ModelAdapterError"
        assert result["message"] == "Test error"
        assert result["provider"] == "test"
        assert result["error_code"] == "TEST_ERROR"

    def test_provider_not_found_error(self):
        """测试提供商不存在异常."""
        exc = ProviderNotFoundError("openai")

        assert "openai" in exc.message
        assert exc.provider == "openai"
        assert exc.error_code == "PROVIDER_NOT_FOUND"

    def test_provider_not_available_error(self):
        """测试提供商不可用异常."""
        exc = ProviderNotAvailableError("claude", reason="API key not set")

        assert "claude" in exc.message
        assert "API key not set" in exc.message
        assert exc.provider == "claude"
        assert exc.error_code == "PROVIDER_NOT_AVAILABLE"

    def test_provider_api_error(self):
        """测试提供商API错误."""
        exc = ProviderAPIError(
            provider="openai",
            message="Invalid API key",
            status_code=401,
            response_body='{"error": "unauthorized"}',
        )

        assert "openai" in exc.message
        assert "Invalid API key" in exc.message
        assert exc.status_code == 401
        assert exc.response_body == '{"error": "unauthorized"}'

    def test_validation_error(self):
        """测试验证错误."""
        exc = RequestValidationError("Invalid field", field="temperature")

        assert "Invalid field" in exc.message
        assert exc.field == "temperature"
        assert exc.error_code == "VALIDATION_ERROR"

    def test_rate_limit_error(self):
        """测试限流错误."""
        exc = RateLimitError(provider="openai", retry_after=60)

        assert "openai" in exc.message
        assert "60 seconds" in exc.message
        assert exc.retry_after == 60

    def test_timeout_error(self):
        """测试超时错误."""
        exc = RequestTimeoutError(provider="claude", timeout=30.0)

        assert "claude" in exc.message
        assert "30" in exc.message
        assert exc.timeout == 30.0
