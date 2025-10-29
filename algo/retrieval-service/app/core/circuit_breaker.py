"""
Circuit Breaker - 熔断器实现
"""

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常状态
    OPEN = "open"  # 熔断开启
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


class CircuitBreaker:
    """
    熔断器实现

    状态转换:
    - CLOSED -> OPEN: 失败率超过阈值
    - OPEN -> HALF_OPEN: 超过恢复时间后尝试恢复
    - HALF_OPEN -> CLOSED: 恢复期间请求成功
    - HALF_OPEN -> OPEN: 恢复期间请求失败
    """

    def __init__(
        self,
        failure_threshold: int = 5,  # 失败阈值
        recovery_timeout: float = 60.0,  # 恢复超时（秒）
        expected_exception: type = Exception,  # 预期的异常类型
        name: str = "circuit_breaker",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        # 检查是否应该从 OPEN 转换到 HALF_OPEN
        if self._state == CircuitState.OPEN and (
            self._last_failure_time
            and time.time() - self._last_failure_time >= self.recovery_timeout
        ):
            logger.info(f"Circuit breaker [{self.name}] entering HALF_OPEN state")
            self._state = CircuitState.HALF_OPEN

        return self._state

    def record_success(self):
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker [{self.name}] recovered, entering CLOSED state")
            self._state = CircuitState.CLOSED

        self._failure_count = 0

    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即重新熔断
            logger.warning(f"Circuit breaker [{self.name}] failed in HALF_OPEN, back to OPEN")
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            # 失败次数超过阈值，熔断
            logger.error(
                f"Circuit breaker [{self.name}] opened due to {self._failure_count} failures"
            )
            self._state = CircuitState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行被保护的函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器开启时
            原始异常: 函数执行失败时
        """
        if self.state == CircuitState.OPEN:
            from app.core.exceptions import CircuitBreakerOpenError

            raise CircuitBreakerOpenError(
                f"Circuit breaker [{self.name}] is OPEN, "
                f"will retry after {self.recovery_timeout}s"
            )

        try:
            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 记录成功
            self.record_success()
            return result

        except self.expected_exception:
            # 记录失败
            self.record_failure()
            raise

    def reset(self):
        """重置熔断器"""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        logger.info(f"Circuit breaker [{self.name}] reset to CLOSED")


class CircuitBreakerRegistry:
    """熔断器注册表 - 管理多个熔断器"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name,
            )
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """获取熔断器"""
        return self._breakers.get(name)

    def reset(self, name: str):
        """重置指定熔断器"""
        if name in self._breakers:
            self._breakers[name].reset()

    def reset_all(self):
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.reset()


# 全局熔断器注册表
circuit_breaker_registry = CircuitBreakerRegistry()
