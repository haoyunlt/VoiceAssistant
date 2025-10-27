"""
OpenTelemetry 分布式追踪集成

为所有 Python 服务提供统一的追踪能力，与 Go 服务的 OpenTelemetry 集成保持一致。
"""

import logging
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

logger = logging.getLogger(__name__)


class TracingConfig:
    """追踪配置"""

    def __init__(
        self,
        service_name: str,
        service_version: str = "1.0.0",
        environment: str = "development",
        otlp_endpoint: Optional[str] = None,
        sampling_rate: float = 1.0,
        enabled: bool = True,
        console_export: bool = False,
    ):
        """
        初始化追踪配置

        Args:
            service_name: 服务名称
            service_version: 服务版本
            environment: 环境（dev/staging/prod）
            otlp_endpoint: OTLP导出端点
            sampling_rate: 采样率 (0.0-1.0)
            enabled: 是否启用
            console_export: 是否输出到控制台（调试用）
        """
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"
        )
        self.sampling_rate = float(os.getenv("OTEL_SAMPLING_RATE", str(sampling_rate)))
        self.enabled = (
            os.getenv("OTEL_ENABLED", str(enabled)).lower() == "true"
        )
        self.console_export = (
            os.getenv("OTEL_CONSOLE_EXPORT", str(console_export)).lower() == "true"
        )


def init_tracing(config: TracingConfig) -> Optional[trace.Tracer]:
    """
    初始化 OpenTelemetry 追踪

    Args:
        config: 追踪配置

    Returns:
        Tracer 实例，如果未启用则返回 None
    """
    if not config.enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return None

    try:
        # 创建资源
        resource = Resource.create(
            {
                SERVICE_NAME: config.service_name,
                SERVICE_VERSION: config.service_version,
                "deployment.environment": config.environment,
            }
        )

        # 创建采样器
        sampler = TraceIdRatioBased(config.sampling_rate)

        # 创建 TracerProvider
        provider = TracerProvider(
            resource=resource,
            sampler=sampler,
        )

        # 添加 OTLP 导出器
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=config.otlp_endpoint,
                insecure=True,  # 生产环境应使用TLS
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                f"OTLP exporter configured: {config.otlp_endpoint}"
            )
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}")

        # 可选：添加控制台导出器（调试用）
        if config.console_export:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("Console exporter enabled")

        # 设置全局 TracerProvider
        trace.set_tracer_provider(provider)

        # 自动 instrument 常用库
        _auto_instrument()

        logger.info(
            f"OpenTelemetry initialized: service={config.service_name}, "
            f"sampling_rate={config.sampling_rate}"
        )

        return trace.get_tracer(config.service_name)

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
        return None


def _auto_instrument():
    """自动 instrument 常用库"""
    try:
        # FastAPI instrument
        FastAPIInstrumentor().instrument()
        logger.debug("FastAPI instrumented")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")

    try:
        # HTTPX instrument（用于HTTP客户端）
        HTTPXClientInstrumentor().instrument()
        logger.debug("HTTPX instrumented")
    except Exception as e:
        logger.warning(f"Failed to instrument HTTPX: {e}")

    try:
        # Redis instrument
        RedisInstrumentor().instrument()
        logger.debug("Redis instrumented")
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")


def get_tracer(name: str) -> trace.Tracer:
    """
    获取 Tracer 实例

    Args:
        name: Tracer 名称（通常是模块名）

    Returns:
        Tracer 实例
    """
    return trace.get_tracer(name)


def get_current_span() -> trace.Span:
    """获取当前 Span"""
    return trace.get_current_span()


def add_span_attributes(**attributes):
    """
    向当前 Span 添加属性

    Args:
        **attributes: 属性键值对
    """
    span = get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, **attributes):
    """
    向当前 Span 添加事件

    Args:
        name: 事件名称
        **attributes: 事件属性
    """
    span = get_current_span()
    if span.is_recording():
        span.add_event(name, attributes)


def record_exception(exc: Exception):
    """
    记录异常到当前 Span

    Args:
        exc: 异常实例
    """
    span = get_current_span()
    if span.is_recording():
        span.record_exception(exc)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))


# 装饰器：为函数添加追踪
def traced(span_name: Optional[str] = None):
    """
    装饰器：为函数添加追踪

    Args:
        span_name: Span 名称（默认使用函数名）

    Usage:
        @traced()
        async def my_function():
            pass
    """
    def decorator(func):
        import functools
        import inspect

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer(__name__)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name) as span:
                try:
                    # 添加参数信息（可选，注意不要泄露敏感信息）
                    if args:
                        span.set_attribute("args.count", len(args))
                    if kwargs:
                        span.set_attribute("kwargs.keys", ",".join(kwargs.keys()))

                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer(__name__)
            name = span_name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(name) as span:
                try:
                    # 添加参数信息
                    if args:
                        span.set_attribute("args.count", len(args))
                    if kwargs:
                        span.set_attribute("kwargs.keys", ",".join(kwargs.keys()))

                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    record_exception(e)
                    raise

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator
