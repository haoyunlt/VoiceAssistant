"""
统一日志配置 - 所有服务使用相同的日志格式和配置
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    service_name: Optional[str] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    配置统一的日志格式

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: 服务名称
        log_format: 自定义日志格式

    Returns:
        配置好的logger实例
    """
    # 默认日志格式
    if log_format is None:
        if service_name:
            log_format = f"%(asctime)s - {service_name} - %(name)s - %(levelname)s - %(message)s"
        else:
            log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 配置根logger
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
    )

    # 返回根logger或服务专属logger
    logger = logging.getLogger(service_name) if service_name else logging.getLogger()
    logger.info(f"Logging configured: level={level}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的logger

    Args:
        name: logger名称（通常使用__name__）

    Returns:
        logger实例
    """
    return logging.getLogger(name)


# 静默第三方库的日志
def silence_noisy_loggers():
    """静默一些第三方库的日志输出"""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
