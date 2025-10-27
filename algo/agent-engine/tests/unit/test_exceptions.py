"""
测试自定义异常
"""

import pytest
from app.core.exceptions import (
    AgentEngineException,
    AuthenticationError,
    AuthorizationError,
    LLMError,
    RateLimitExceededError,
    ServiceNotInitializedException,
    TaskExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
    ValidationError,
)


def test_agent_engine_exception():
    """测试基础异常"""
    exc = AgentEngineException("Test error", "TEST_ERROR")
    assert exc.message == "Test error"
    assert exc.error_code == "TEST_ERROR"
    assert str(exc) == "Test error"


def test_service_not_initialized_exception():
    """测试服务未初始化异常"""
    exc = ServiceNotInitializedException("Test Service")
    assert "Test Service not initialized" in exc.message
    assert exc.error_code == "SERVICE_NOT_INITIALIZED"


def test_validation_error():
    """测试验证错误"""
    exc = ValidationError("Invalid value", field="test_field")
    assert exc.message == "Invalid value"
    assert exc.field == "test_field"
    assert exc.error_code == "VALIDATION_ERROR"


def test_task_execution_error():
    """测试任务执行错误"""
    exc = TaskExecutionError("Execution failed", task="test task")
    assert exc.message == "Execution failed"
    assert exc.task == "test task"
    assert exc.error_code == "TASK_EXECUTION_ERROR"


def test_tool_not_found_error():
    """测试工具未找到错误"""
    exc = ToolNotFoundError("calculator")
    assert "calculator" in exc.message
    assert exc.tool_name == "calculator"
    assert exc.error_code == "TOOL_NOT_FOUND"


def test_tool_registration_error():
    """测试工具注册错误"""
    exc = ToolRegistrationError("Registration failed", tool_name="test_tool")
    assert exc.message == "Registration failed"
    assert exc.tool_name == "test_tool"
    assert exc.error_code == "TOOL_REGISTRATION_ERROR"


def test_llm_error():
    """测试 LLM 错误"""
    exc = LLMError("API error", provider="openai")
    assert exc.message == "API error"
    assert exc.provider == "openai"
    assert exc.error_code == "LLM_ERROR"


def test_authentication_error():
    """测试认证错误"""
    exc = AuthenticationError("Invalid token")
    assert exc.message == "Invalid token"
    assert exc.error_code == "AUTHENTICATION_ERROR"


def test_authorization_error():
    """测试授权错误"""
    exc = AuthorizationError("Access denied", required_permission="admin:write")
    assert exc.message == "Access denied"
    assert exc.required_permission == "admin:write"
    assert exc.error_code == "AUTHORIZATION_ERROR"


def test_rate_limit_exceeded_error():
    """测试限流错误"""
    exc = RateLimitExceededError("Too many requests", retry_after=60)
    assert exc.message == "Too many requests"
    assert exc.retry_after == 60
    assert exc.error_code == "RATE_LIMIT_EXCEEDED"
