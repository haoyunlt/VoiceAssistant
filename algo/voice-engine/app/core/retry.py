"""
重试机制 - 带指数退避
"""

import asyncio
import logging
import random
from collections.abc import Callable

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    **kwargs,
):
    """
    带指数退避的重试机制

    Args:
        func: 要重试的函数
        *args: 位置参数
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        exceptions: 需要重试的异常类型
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次尝试的异常
    """

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                raise

            # 计算延迟
            delay = min(initial_delay * (exponential_base**attempt), max_delay)

            # 添加随机抖动
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.2f}s..."
            )

            await asyncio.sleep(delay)

    # 不应该到达这里
    raise last_exception
