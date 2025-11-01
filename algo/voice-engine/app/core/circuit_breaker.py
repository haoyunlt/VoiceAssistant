"""
熔断器模式 - 用于外部服务调用
"""

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


class CircuitBreaker:
    """
    熔断器

    当失败率超过阈值时，打开熔断器，拒绝请求
    经过一段时间后，进入半开状态，尝试恢复
    """

    def __init__(
        self,
        failure_threshold: int = 5,  # 失败次数阈值
        recovery_timeout: int = 60,  # 恢复超时（秒）
        expected_exception: type = Exception,
        name: str = "circuit_breaker",
    ):
        """
        初始化熔断器

        Args:
            failure_threshold: 失败次数阈值
            recovery_timeout: 恢复超时（秒）
            expected_exception: 预期的异常类型
            name: 熔断器名称
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = CircuitState.CLOSED

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s"
        )

    async def call(self, func: Callable, *args, **kwargs):
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开时
            原始异常: 函数调用失败时
        """

        # 检查熔断器状态
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. Retry after {self.recovery_timeout}s"
                )

        try:
            # 调用函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 成功：重置计数器
            self._on_success()

            return result

        except self.expected_exception:
            # 失败：增加计数器
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True

        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """成功回调"""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' recovered to CLOSED state")
            self.state = CircuitState.CLOSED

        self.failure_count = 0

    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        logger.warning(
            f"Circuit breaker '{self.name}' failure count: "
            f"{self.failure_count}/{self.failure_threshold}"
        )

        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker '{self.name}' opened due to "
                f"{self.failure_count} consecutive failures"
            )
            self.state = CircuitState.OPEN

    def reset(self):
        """手动重置熔断器"""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def get_state(self) -> dict:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    pass
