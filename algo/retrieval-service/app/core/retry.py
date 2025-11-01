"""
Retry mechanism - 重试机制
"""

import asyncio
import builtins
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


async def retry_async(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable | None = None,
    **kwargs,
) -> Any:
    """
    异步函数重试装饰器

    Args:
        func: 要重试的异步函数
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子（指数退避）
        max_delay: 最大延迟（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
        *args, **kwargs: 函数参数

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                raise

            # 计算延迟时间（指数退避）
            actual_delay = min(delay, max_delay)

            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {actual_delay:.2f}s: {e}"
            )

            # 调用重试回调
            if on_retry:
                try:
                    if asyncio.iscoroutinefunction(on_retry):
                        await on_retry(attempt, e)
                    else:
                        on_retry(attempt, e)
                except Exception as callback_error:
                    logger.error(f"Retry callback failed: {callback_error}")

            # 等待后重试
            await asyncio.sleep(actual_delay)

            # 增加延迟（指数退避）
            delay *= backoff_factor

    # 理论上不会到达这里
    raise last_exception


def with_timeout(timeout: float):
    """
    为异步函数添加超时控制

    Args:
        timeout: 超时时间（秒）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except builtins.TimeoutError:
                from app.core.exceptions import TimeoutError

                logger.error(f"Function {func.__name__} timed out after {timeout}s")
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout}s") from None

        return wrapper

    return decorator
