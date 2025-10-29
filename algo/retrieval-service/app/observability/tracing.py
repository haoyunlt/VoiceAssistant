"""
OpenTelemetry Tracing - 分布式追踪
"""

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def setup_tracing(
    service_name: str = "retrieval-service",
    service_version: str = "1.0.0",
    endpoint: str | None = None,
    enabled: bool = True,
):
    """
    设置 OpenTelemetry 追踪

    Args:
        service_name: 服务名称
        service_version: 服务版本
        endpoint: OTLP 导出器端点（如 Jaeger）
        enabled: 是否启用追踪
    """
    if not enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return

    if not endpoint:
        logger.warning("OpenTelemetry endpoint not configured, tracing disabled")
        return

    try:
        # 创建资源
        resource = Resource(
            attributes={
                SERVICE_NAME: service_name,
                SERVICE_VERSION: service_version,
            }
        )

        # 创建 TracerProvider
        provider = TracerProvider(resource=resource)

        # 创建 OTLP 导出器
        otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True,  # 生产环境应该使用 TLS
        )

        # 添加 Span 处理器
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # 设置全局 TracerProvider
        trace.set_tracer_provider(provider)

        # 自动instrument FastAPI
        FastAPIInstrumentor().instrument()

        # 自动instrument HTTPX（用于HTTP客户端调用）
        HTTPXClientInstrumentor().instrument()

        logger.info(
            f"OpenTelemetry tracing enabled: service={service_name}, endpoint={endpoint}"
        )

    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry tracing: {e}")


def get_tracer(name: str = __name__):
    """获取 Tracer"""
    return trace.get_tracer(name)


def get_current_span():
    """获取当前 Span"""
    return trace.get_current_span()


def add_span_attributes(**attributes):
    """添加 Span 属性"""
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict | None = None):
    """添加 Span 事件"""
    span = get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})
