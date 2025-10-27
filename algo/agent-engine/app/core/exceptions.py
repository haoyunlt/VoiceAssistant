"""
自定义异常类
"""


class AgentEngineException(Exception):
    """Agent Engine 基础异常"""

    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)


class ServiceNotInitializedException(AgentEngineException):
    """服务未初始化异常"""

    def __init__(self, service_name: str = "Agent Engine"):
        super().__init__(
            message=f"{service_name} not initialized",
            error_code="SERVICE_NOT_INITIALIZED"
        )


class ValidationError(AgentEngineException):
    """验证错误"""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, error_code="VALIDATION_ERROR")


class TaskExecutionError(AgentEngineException):
    """任务执行错误"""

    def __init__(self, message: str, task: str = None):
        self.task = task
        super().__init__(message, error_code="TASK_EXECUTION_ERROR")


class ToolNotFoundError(AgentEngineException):
    """工具未找到错误"""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(
            message=f"Tool '{tool_name}' not found",
            error_code="TOOL_NOT_FOUND"
        )


class ToolExecutionError(AgentEngineException):
    """工具执行错误"""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {message}",
            error_code="TOOL_EXECUTION_ERROR"
        )


class ToolRegistrationError(AgentEngineException):
    """工具注册错误"""

    def __init__(self, message: str, tool_name: str = None):
        self.tool_name = tool_name
        super().__init__(message, error_code="TOOL_REGISTRATION_ERROR")


class LLMError(AgentEngineException):
    """LLM 服务错误"""

    def __init__(self, message: str, provider: str = None):
        self.provider = provider
        super().__init__(message, error_code="LLM_ERROR")


class LLMTimeoutError(LLMError):
    """LLM 超时错误"""

    def __init__(self, provider: str = None):
        super().__init__(
            message="LLM request timeout",
            provider=provider
        )
        self.error_code = "LLM_TIMEOUT"


class MemoryError(AgentEngineException):
    """记忆管理错误"""

    def __init__(self, message: str, conversation_id: str = None):
        self.conversation_id = conversation_id
        super().__init__(message, error_code="MEMORY_ERROR")


class ConfigurationError(AgentEngineException):
    """配置错误"""

    def __init__(self, message: str, config_key: str = None):
        self.config_key = config_key
        super().__init__(message, error_code="CONFIGURATION_ERROR")


class AuthenticationError(AgentEngineException):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, error_code="AUTHENTICATION_ERROR")


class AuthorizationError(AgentEngineException):
    """授权错误"""

    def __init__(self, message: str = "Permission denied", required_permission: str = None):
        self.required_permission = required_permission
        super().__init__(message, error_code="AUTHORIZATION_ERROR")


class RateLimitExceededError(AgentEngineException):
    """限流错误"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED")


class ResourceNotFoundError(AgentEngineException):
    """资源未找到错误"""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            error_code="RESOURCE_NOT_FOUND"
        )


class MaxRetriesExceededError(AgentEngineException):
    """最大重试次数错误"""

    def __init__(self, operation: str, max_retries: int):
        self.operation = operation
        self.max_retries = max_retries
        super().__init__(
            message=f"Max retries ({max_retries}) exceeded for operation: {operation}",
            error_code="MAX_RETRIES_EXCEEDED"
        )
