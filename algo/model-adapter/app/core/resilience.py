"""韧性组件 - 重试和熔断器."""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pybreaker import CircuitBreaker, CircuitBreakerError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar("T")


# 全局熔断器存储
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, fail_max: int = 5, timeout: int = 30) -> CircuitBreaker:
    """
    获取或创建熔断器.

    Args:
        name: 熔断器名称 (通常是provider名称)
        fail_max: 失败阈值 (连续失败多少次后打开)
        timeout: 半开状态尝试时间 (秒)

    Returns:
        熔断器实例
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            fail_max=fail_max,
            timeout_duration=timeout,
            name=name,
        )
        logger.info(f"Created circuit breaker for {name}: fail_max={fail_max}, timeout={timeout}s")

    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """
    获取所有熔断器.

    Returns:
        熔断器字典
    """
    return _circuit_breakers


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 4.0,
    retry_exceptions: tuple = (Exception,),
):
    """
    重试装饰器.

    指数退避: min_wait -> min_wait*2 -> max_wait

    Args:
        max_attempts: 最大尝试次数
        min_wait: 最小等待时间(秒)
        max_wait: 最大等待时间(秒)
        retry_exceptions: 需要重试的异常类型

    Example:
        @with_retry(max_attempts=3, min_wait=1, max_wait=4)
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
                    retry=retry_if_exception_type(retry_exceptions),
                    reraise=True,
                ):
                    with attempt:
                        return await func(*args, **kwargs)
            except RetryError as e:
                logger.error(
                    f"Failed after {max_attempts} attempts: {func.__name__}",
                    exc_info=e.last_attempt.exception(),
                )
                # 重新抛出原始异常
                raise e.last_attempt.exception()

        return wrapper

    return decorator


def with_circuit_breaker(provider_name: str, fail_max: int = 5, timeout: int = 30):
    """
    熔断器装饰器.

    Args:
        provider_name: 提供商名称
        fail_max: 失败阈值
        timeout: 半开状态尝试时间(秒)

    Example:
        @with_circuit_breaker("openai", fail_max=5, timeout=30)
        async def call_openai():
            ...
    """
    def decorator(func: Callable) -> Callable:
        breaker = get_circuit_breaker(provider_name, fail_max, timeout)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await breaker.call_async(func, *args, **kwargs)
            except CircuitBreakerError as e:
                logger.warning(
                    f"Circuit breaker open for {provider_name}: {e}",
                    extra={
                        "provider": provider_name,
                        "breaker_state": breaker.current_state,
                        "fail_counter": breaker.fail_counter,
                    },
                )
                raise RuntimeError(
                    f"Provider {provider_name} is temporarily unavailable (circuit breaker open)"
                ) from e

        return wrapper

    return decorator


def with_timeout(seconds: float):
    """
    超时装饰器.

    Args:
        seconds: 超时时间(秒)

    Example:
        @with_timeout(30.0)
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"Timeout after {seconds}s: {func.__name__}")
                raise RuntimeError(f"Request timeout after {seconds}s")

        return wrapper

    return decorator


def with_resilience(
    provider_name: str,
    max_attempts: int = 3,
    timeout: float = 60.0,
    fail_max: int = 5,
    breaker_timeout: int = 30,
    retry_exceptions: tuple = (Exception,),
):
    """
    组合装饰器: 超时 + 重试 + 熔断器.

    执行顺序: timeout -> retry -> circuit_breaker

    Args:
        provider_name: 提供商名称
        max_attempts: 重试次数
        timeout: 单次请求超时(秒)
        fail_max: 熔断器失败阈值
        breaker_timeout: 熔断器半开时间(秒)
        retry_exceptions: 需要重试的异常

    Example:
        @with_resilience("openai", max_attempts=3, timeout=60.0)
        async def call_openai():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 先应用熔断器 (最外层)
        func = with_circuit_breaker(provider_name, fail_max, breaker_timeout)(func)

        # 再应用重试 (中层)
        func = with_retry(max_attempts, retry_exceptions=retry_exceptions)(func)

        # 最后应用超时 (最内层，每次尝试都有超时)
        func = with_timeout(timeout)(func)

        return func

    return decorator


class StreamErrorHandler:
    """流式响应错误处理器."""

    @staticmethod
    async def wrap_stream_with_error_handling(
        stream_generator,
        provider: str,
        model: str,
        heartbeat_interval: float = 10.0,
    ):
        """
        包装流式生成器，增加错误处理和心跳.

        Args:
            stream_generator: 原始流式生成器
            provider: 提供商名称
            model: 模型名称
            heartbeat_interval: 心跳间隔(秒)

        Yields:
            包装后的chunk (包含错误事件和心跳)
        """
        last_heartbeat = asyncio.get_event_loop().time()
        chunk_count = 0

        try:
            async for chunk in stream_generator:
                # 发送正常chunk
                yield {
                    "type": "chunk",
                    "data": chunk,
                }

                chunk_count += 1

                # 检查是否需要发送心跳
                now = asyncio.get_event_loop().time()
                if now - last_heartbeat > heartbeat_interval:
                    yield {
                        "type": "heartbeat",
                        "data": {
                            "provider": provider,
                            "model": model,
                            "chunks_sent": chunk_count,
                            "timestamp": now,
                        },
                    }
                    last_heartbeat = now

            # 流正常结束
            yield {
                "type": "done",
                "data": {
                    "provider": provider,
                    "model": model,
                    "total_chunks": chunk_count,
                },
            }

        except asyncio.TimeoutError as e:
            logger.error(f"Stream timeout for {provider}/{model}")
            yield {
                "type": "error",
                "data": {
                    "error": "StreamTimeout",
                    "message": f"Stream timeout for {provider}/{model}",
                    "provider": provider,
                    "model": model,
                },
            }

        except Exception as e:
            logger.error(
                f"Stream error for {provider}/{model}: {e}",
                exc_info=True,
            )
            yield {
                "type": "error",
                "data": {
                    "error": type(e).__name__,
                    "message": str(e),
                    "provider": provider,
                    "model": model,
                },
            }

    @staticmethod
    def format_as_sse(event: dict[str, Any]) -> str:
        """
        将事件格式化为SSE格式.

        Args:
            event: 事件字典

        Returns:
            SSE格式字符串
        """
        import json

        event_type = event.get("type", "message")
        data = event.get("data", {})

        lines = []
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        lines.append("")  # 空行表示事件结束

        return "\n".join(lines) + "\n"


# 指标收集 (Prometheus)
from prometheus_client import Counter, Gauge, Histogram

# 重试指标
retry_total = Counter(
    "model_adapter_retry_total",
    "Total number of retries",
    ["provider", "reason"],
)

# 熔断器状态
circuit_breaker_state = Gauge(
    "model_adapter_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["provider"],
)

# 超时次数
timeout_total = Counter(
    "model_adapter_timeout_total",
    "Total number of timeouts",
    ["provider", "operation"],
)

# 流式错误
stream_error_total = Counter(
    "model_adapter_stream_error_total",
    "Total number of stream errors",
    ["provider", "error_type"],
)


def update_circuit_breaker_metrics():
    """更新熔断器指标."""
    for name, breaker in _circuit_breakers.items():
        state_map = {
            "open": 1,
            "closed": 0,
            "half-open": 2,
        }
        state_value = state_map.get(breaker.current_state, -1)
        circuit_breaker_state.labels(provider=name).set(state_value)
