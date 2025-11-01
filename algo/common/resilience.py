"""
弹性机制：熔断器、重试、超时控制

提供与 Go 服务 pkg/resilience 对等的功能
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 关闭状态，正常工作
    OPEN = "open"  # 打开状态，快速失败
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


@dataclass
class CircuitBreakerStats:
    """熔断器统计信息"""

    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    state_changed_at: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    熔断器实现

    当连续失败次数达到阈值时打开熔断器，一段时间后进入半开状态尝试恢复。
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] | tuple[type[Exception], ...] = Exception,
        half_open_max_calls: int = 1,
    ):
        """
        初始化熔断器

        Args:
            name: 熔断器名称（用于日志和监控）
            failure_threshold: 触发熔断的连续失败次数阈值
            recovery_timeout: 从打开到半开的等待时间（秒）
            expected_exception: 期望捕获的异常类型
            half_open_max_calls: 半开状态下允许的最大并发调用数
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call_async(self, func: Callable, *args, **kwargs):
        """
        异步调用（带熔断保护）

        Args:
            func: 要调用的异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            Exception: 如果熔断器打开或函数执行失败
        """
        async with self._lock:
            self.stats.total_requests += 1

            # 检查状态
            if self.state == CircuitState.OPEN:
                if time.time() - self.stats.state_changed_at > self.recovery_timeout:
                    self._transition_to_half_open()
                else:
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN, "
                        f"failing fast (failures: {self.stats.failure_count})"
                    )
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN")

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    logger.debug(
                        f"Circuit breaker '{self.name}' in HALF_OPEN, max concurrent calls reached"
                    )
                    raise Exception(f"Circuit breaker '{self.name}' is HALF_OPEN and at capacity")

                self._half_open_calls += 1

        # 执行函数
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except self.expected_exception as e:
            await self._on_failure(e)
            raise

        finally:
            if self.state == CircuitState.HALF_OPEN:
                async with self._lock:
                    self._half_open_calls -= 1

    def call_sync(self, func: Callable, *args, **kwargs):
        """
        同步调用（带熔断保护）

        Args:
            func: 要调用的同步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果
        """
        self.stats.total_requests += 1

        # 检查状态
        if self.state == CircuitState.OPEN:
            if time.time() - self.stats.state_changed_at > self.recovery_timeout:
                self._transition_to_half_open()
            else:
                logger.warning(f"Circuit breaker '{self.name}' is OPEN, failing fast")
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")

        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise Exception(f"Circuit breaker '{self.name}' is HALF_OPEN and at capacity")

            self._half_open_calls += 1

        # 执行函数
        try:
            result = func(*args, **kwargs)
            self._on_success_sync()
            return result

        except self.expected_exception as e:
            self._on_failure_sync(e)
            raise

        finally:
            if self.state == CircuitState.HALF_OPEN:
                self._half_open_calls -= 1

    async def _on_success(self):
        """成功回调"""
        async with self._lock:
            self._on_success_sync()

    def _on_success_sync(self):
        """成功回调（同步版本）"""
        self.stats.success_count += 1
        self.stats.consecutive_failures = 0
        self.stats.last_success_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' recovered and CLOSED")

    async def _on_failure(self, exc: Exception):
        """失败回调"""
        async with self._lock:
            self._on_failure_sync(exc)

    def _on_failure_sync(self, exc: Exception):
        """失败回调（同步版本）"""
        self.stats.failure_count += 1
        self.stats.consecutive_failures += 1
        self.stats.last_failure_time = time.time()

        logger.warning(
            f"Circuit breaker '{self.name}' recorded failure: "
            f"{self.stats.consecutive_failures}/{self.failure_threshold} - {exc}"
        )

        if self.stats.consecutive_failures >= self.failure_threshold:
            self._transition_to_open()
            logger.error(
                f"Circuit breaker '{self.name}' OPENED after "
                f"{self.stats.consecutive_failures} consecutive failures"
            )

    def _transition_to_open(self):
        """转换到打开状态"""
        self.state = CircuitState.OPEN
        self.stats.state_changed_at = time.time()

    def _transition_to_half_open(self):
        """转换到半开状态"""
        self.state = CircuitState.HALF_OPEN
        self.stats.state_changed_at = time.time()
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' entering HALF_OPEN state")

    def _transition_to_closed(self):
        """转换到关闭状态"""
        self.state = CircuitState.CLOSED
        self.stats.state_changed_at = time.time()
        self.stats.consecutive_failures = 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.stats.total_requests,
            "success_count": self.stats.success_count,
            "failure_count": self.stats.failure_count,
            "consecutive_failures": self.stats.consecutive_failures,
            "failure_rate": (
                self.stats.failure_count / self.stats.total_requests
                if self.stats.total_requests > 0
                else 0
            ),
            "last_failure_time": self.stats.last_failure_time,
            "last_success_time": self.stats.last_success_time,
        }


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
):
    """
    重试装饰器

    Args:
        max_attempts: 最大尝试次数
        backoff_base: 指数退避基数
        backoff_max: 最大退避时间（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数 (attempt_number, exception)

    Usage:
        @with_retry(max_attempts=3, exceptions=(httpx.TimeoutException,))
        async def call_external_api():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"Function '{func.__name__}' failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # 计算退避时间
                    wait_time = min(backoff_base ** (attempt - 1), backoff_max)

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for '{func.__name__}': {e}. "
                        f"Retrying in {wait_time:.2f}s..."
                    )

                    # 调用回调
                    if on_retry:
                        on_retry(attempt, e)

                    await asyncio.sleep(wait_time)

            # 不应该到达这里，但为了类型安全
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"Function '{func.__name__}' failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    wait_time = min(backoff_base ** (attempt - 1), backoff_max)

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for '{func.__name__}': {e}. "
                        f"Retrying in {wait_time:.2f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(wait_time)

            raise last_exception

        import inspect

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


async def with_timeout(coro, timeout: float, timeout_exception: type[Exception] | None = None):
    """
    为协程添加超时控制

    Args:
        coro: 协程对象
        timeout: 超时时间（秒）
        timeout_exception: 超时时抛出的异常类型

    Returns:
        协程执行结果

    Raises:
        asyncio.TimeoutError 或 timeout_exception
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError as e:
        if timeout_exception:
            raise timeout_exception(f"Operation timed out after {timeout}s") from e
        raise
