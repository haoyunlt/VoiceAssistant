"""
Logging Configuration
日志配置
"""

import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logging(log_level: str = "INFO"):
    """
    设置日志配置

    Args:
        log_level: 日志级别
    """
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 清除已存在的处理器
    root_logger.handlers.clear()

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # JSON格式化器（生产环境）
    json_formatter = jsonlogger.JsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        rename_fields={
            "timestamp": "@timestamp",
            "level": "level",
            "name": "logger",
            "message": "message",
        },
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # 简单格式化器（开发环境）
    simple_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 根据环境选择格式化器
    import os

    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        console_handler.setFormatter(json_formatter)
    else:
        console_handler.setFormatter(simple_formatter)

    root_logger.addHandler(console_handler)

    # 设置第三方库日志级别
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info(f"Logging configured with level: {log_level}")
