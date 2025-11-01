"""
统一的结构化日志配置

提供：
- JSON 格式的结构化日志
- 请求ID追踪
- Trace ID 集成
- 多环境日志级别管理
"""

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any

# 请求ID上下文变量
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class StructuredFormatter(logging.Formatter):
    """
    结构化 JSON 日志格式化器

    输出格式:
    {
        "timestamp": "2025-01-01T12:00:00.000Z",
        "level": "INFO",
        "logger": "module.name",
        "message": "log message",
        "request_id": "uuid",
        "trace_id": "hex",
        "service": "service-name",
        ...额外字段
    }
    """

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        # 添加请求ID
        if request_id := request_id_var.get(""):
            log_data["request_id"] = request_id

        # 添加 trace_id（从 OpenTelemetry）
        try:
            from .telemetry import get_current_span

            span = get_current_span()
            if span.is_recording():
                span_context = span.get_span_context()
                log_data["trace_id"] = format(span_context.trace_id, "032x")
                log_data["span_id"] = format(span_context.span_id, "016x")
        except Exception:
            pass

        # 添加额外字段（通过 extra 参数传递）
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        # 添加文件和行号信息（仅在DEBUG级别）
        if record.levelno == logging.DEBUG:
            log_data["file"] = record.filename
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName

        # 添加异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data, ensure_ascii=False, default=str)


class RequestIDFilter(logging.Filter):
    """请求ID过滤器（用于非结构化日志格式）"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")
        return True


def setup_logging(
    service_name: str,
    log_level: str | None = None,
    use_json: bool | None = None,
) -> None:
    """
    配置统一日志

    Args:
        service_name: 服务名称
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        use_json: 是否使用 JSON 格式（默认根据环境判断）
    """
    # 从环境变量获取配置
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    if use_json is None:
        env = os.getenv("ENV", "development").lower()
        use_json = env in ("staging", "production")

    # 移除已有的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建处理器
    handler = logging.StreamHandler(sys.stdout)

    # 设置格式化器
    if use_json:
        formatter: logging.Formatter = StructuredFormatter(service_name)
    else:
        # 开发环境使用更可读的格式
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.addFilter(RequestIDFilter())

    handler.setFormatter(formatter)

    # 配置根日志器
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.addHandler(handler)

    # 设置第三方库的日志级别（避免过多输出）
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info(f"Logging configured: service={service_name}, level={log_level}, json={use_json}")


def set_request_id(request_id: str) -> None:
    """
    设置当前请求ID

    Args:
        request_id: 请求ID
    """
    request_id_var.set(request_id)


def get_request_id() -> str:
    """
    获取当前请求ID

    Returns:
        请求ID，如果未设置则返回空字符串
    """
    return request_id_var.get("")


def clear_request_id() -> None:
    """清除请求ID"""
    request_id_var.set("")


# 日志辅助函数
def log_with_context(logger: logging.Logger, level: int, message: str, **extra: Any) -> None:
    """
    带上下文的日志记录

    Args:
        logger: Logger 实例
        level: 日志级别
        message: 日志消息
        **extra: 额外字段
    """
    logger.log(level, message, extra=extra)


# FastAPI 中间件
async def logging_middleware(request, call_next):
    """
    日志中间件

    自动设置请求ID，并记录请求日志

    Usage:
        from fastapi import FastAPI
        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)
    """
    import time
    import uuid

    # 设置请求ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_id(request_id)

    # 记录请求开始
    start_time = time.time()
    logger = logging.getLogger(__name__)

    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "event": "request_start",
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
        },
    )

    try:
        response = await call_next(request)

        # 记录请求完成
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "event": "request_complete",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # 添加请求ID到响应头
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as e:
        # 记录请求失败
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {request.method} {request.url.path} - {str(e)}",
            extra={
                "event": "request_error",
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            },
            exc_info=True,
        )
        raise

    finally:
        clear_request_id()
