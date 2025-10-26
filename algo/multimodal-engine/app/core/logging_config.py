"""
Logging configuration
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """配置日志"""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)
