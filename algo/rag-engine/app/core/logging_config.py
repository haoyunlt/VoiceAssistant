"""日志配置"""
import logging
import sys

from app.core.config import settings


def setup_logging():
    """设置日志"""
    log_level = getattr(logging, settings.LOG_LEVEL.upper())

    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
