"""
异常体系单元测试
"""

import pytest

from algo.common.exceptions import (
    ResourceNotFoundError,
    ServiceUnavailableError,
    ValidationError,
    VoiceAssistantError,
    get_http_status_code,
    handle_service_error,
    wrap_exception,
)


class TestVoiceAssistantError:
    """基础异常测试"""

    def test_basic_error(self):
        """测试基本异常"""
        error = VoiceAssistantError("Test error")
        assert str(error) == "Test error (code=VoiceAssistantError)"
        assert error.message == "Test error"
        assert error.code == "VoiceAssistantError"

    def test_error_with_code(self):
        """测试带错误代码的异常"""
        error = VoiceAssistantError("Test error", code="TEST_001")
        assert error.code == "TEST_001"

    def test_error_with_details(self):
        """测试带详情的异常"""
        details = {"field": "username", "value": "test"}
        error = VoiceAssistantError("Test error", details=details)
        assert error.details == details
        assert "details" in str(error)

    def test_error_with_cause(self):
        """测试带原因的异常"""
        cause = ValueError("Original error")
        error = VoiceAssistantError("Wrapped error", cause=cause)
        assert error.cause == cause

    def test_to_dict(self):
        """测试转换为字典"""
        error = VoiceAssistantError(
            "Test error",
            code="TEST_001",
            details={"key": "value"}
        )
        error_dict = error.to_dict()

        assert error_dict["error"] == "TEST_001"
        assert error_dict["message"] == "Test error"
        assert error_dict["details"] == {"key": "value"}


class TestSpecificErrors:
    """特定异常类型测试"""

    def test_service_unavailable(self):
        """测试服务不可用异常"""
        error = ServiceUnavailableError("Service is down")
        assert isinstance(error, VoiceAssistantError)
        assert error.code == "ServiceUnavailableError"

    def test_resource_not_found(self):
        """测试资源未找到异常"""
        error = ResourceNotFoundError("Resource not found", code="NOT_FOUND")
        assert error.code == "NOT_FOUND"

    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError(
            "Invalid input",
            details={"field": "email", "error": "invalid format"}
        )
        assert error.details["field"] == "email"


class TestWrapException:
    """异常包装测试"""

    def test_wrap_basic_exception(self):
        """测试包装基本异常"""
        original = ValueError("Original error")
        wrapped = wrap_exception(original)

        assert isinstance(wrapped, VoiceAssistantError)
        assert wrapped.cause == original
        assert "ValueError" in wrapped.details["original_type"]

    def test_wrap_with_custom_message(self):
        """测试包装时使用自定义消息"""
        original = ValueError("Original error")
        wrapped = wrap_exception(original, message="Custom message")

        assert wrapped.message == "Custom message"

    def test_wrap_with_custom_class(self):
        """测试包装为指定异常类"""
        original = ValueError("Original error")
        wrapped = wrap_exception(original, error_class=ServiceUnavailableError)

        assert isinstance(wrapped, ServiceUnavailableError)


class TestHandleServiceError:
    """服务错误处理测试"""

    def test_handle_timeout(self):
        """测试处理超时错误"""
        import httpx

        original = httpx.TimeoutException("Request timeout")
        handled = handle_service_error(original, "test-service")

        assert isinstance(handled, VoiceAssistantError)
        assert "timeout" in handled.message.lower()
        assert handled.details["service"] == "test-service"

    def test_handle_connection_error(self):
        """测试处理连接错误"""
        import httpx

        original = httpx.ConnectError("Connection failed")
        handled = handle_service_error(original, "test-service")

        assert isinstance(handled, ServiceUnavailableError)
        assert "unavailable" in handled.message.lower()


class TestHttpStatusCodeMapping:
    """HTTP 状态码映射测试"""

    def test_not_found_404(self):
        """测试 404 映射"""
        error = ResourceNotFoundError("Not found")
        assert get_http_status_code(error) == 404

    def test_validation_400(self):
        """测试 400 映射"""
        error = ValidationError("Invalid input")
        assert get_http_status_code(error) == 400

    def test_service_unavailable_503(self):
        """测试 503 映射"""
        error = ServiceUnavailableError("Service down")
        assert get_http_status_code(error) == 503

    def test_default_500(self):
        """测试默认 500"""
        error = VoiceAssistantError("Generic error")
        assert get_http_status_code(error) == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
