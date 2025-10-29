"""
Structured Logging - 结构化日志
"""

import logging
import sys
from typing import Any

from loguru import logger as loguru_logger


class InterceptHandler(logging.Handler):
    """拦截标准日志库的日志，转发到 loguru"""

    def emit(self, record: logging.LogRecord):
        # 获取对应的 loguru level
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    level: str = "INFO",
    json_logs: bool = False,
    service_name: str = "retrieval-service",
):
    """
    设置结构化日志

    Args:
        level: 日志级别
        json_logs: 是否输出JSON格式
        service_name: 服务名称
    """
    # 移除默认的 handler
    loguru_logger.remove()

    # 配置日志格式
    if json_logs:
        # JSON 格式（生产环境）
        log_format = (
            "{"
            '"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}",'
            '"level": "{level}",'
            '"service": "' + service_name + '",'
            '"logger": "{name}",'
            '"message": "{message}",'
            '"extra": {extra}'
            "}"
        )
    else:
        # 人类可读格式（开发环境）
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level> | "
            "{extra}"
        )

    # 添加 stdout handler
    loguru_logger.add(
        sys.stdout,
        format=log_format,
        level=level,
        serialize=json_logs,
        backtrace=True,
        diagnose=True,
    )

    # 拦截标准日志库
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 替换已存在的 logger
    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).handlers = []
        logging.getLogger(logger_name).propagate = True


def bind_request_context(request_id: str, **kwargs: Any):
    """
    绑定请求上下文到日志

    Args:
        request_id: 请求ID
        **kwargs: 其他上下文信息
    """
    return loguru_logger.bind(request_id=request_id, **kwargs)


# 导出 loguru logger 作为默认 logger
logger = loguru_logger
