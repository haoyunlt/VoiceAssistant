"""
重试装饰器
"""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps

logger = logging.getLogger(__name__)


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable | None = None,
):
    """
    异步重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避因子
        exceptions: 需要重试的异常类型
        on_retry: 重试回调函数
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )

                        # 调用重试回调
                        if on_retry:
                            try:
                                await on_retry(attempt, e)
                            except Exception as callback_error:
                                logger.error(f"Retry callback error: {callback_error}")

                        # 等待后重试
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries} retries failed for {func.__name__}: {e}"
                        )

            # 所有重试都失败，抛出最后一个异常
            raise last_exception

        return wrapper

    return decorator


def sync_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    同步重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避因子
        exceptions: 需要重试的异常类型
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay}s..."
                        )

                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_retries} retries failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


class RetryContext:
    """重试上下文（用于条件重试）"""

    def __init__(self, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.attempt = 0
        self.last_exception = None

    async def execute(
        self, func: Callable, *args, exceptions: tuple[type[Exception], ...] = (Exception,), **kwargs
    ):
        """执行带重试的函数"""
        current_delay = self.delay

        for attempt in range(self.max_retries + 1):
            self.attempt = attempt
            try:
                return await func(*args, **kwargs)

            except exceptions as e:
                self.last_exception = e

                if attempt < self.max_retries:
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= self.backoff
                else:
                    logger.error(f"All {self.max_retries} retries failed: {e}")

        raise self.last_exception
