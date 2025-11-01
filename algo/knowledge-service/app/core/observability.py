"""
Observability Configuration
可观测性配置 - OpenTelemetry
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局tracer实例
_tracer: object | None = None


def setup_observability():
    """
    设置OpenTelemetry可观测性
    """
    global _tracer

    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # 创建Resource
        resource = Resource(
            attributes={
                SERVICE_NAME: settings.OTEL_SERVICE_NAME,
                "service.version": settings.VERSION,
                "service.environment": settings.ENVIRONMENT,
            }
        )

        # 创建TracerProvider
        provider = TracerProvider(resource=resource)

        # 添加OTLP导出器
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,  # 使用http而不是https
        )
        processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(processor)

        # 设置全局TracerProvider
        trace.set_tracer_provider(provider)

        # 获取tracer
        _tracer = trace.get_tracer(__name__)

        logger.info(f"OpenTelemetry initialized: {settings.OTEL_EXPORTER_OTLP_ENDPOINT}")

        return _tracer

    except ImportError as e:
        logger.warning(f"OpenTelemetry not installed: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to setup OpenTelemetry: {e}")
        return None


def instrument_app(app):
    """
    为FastAPI应用添加instrumentation

    Args:
        app: FastAPI应用实例
    """
    if not settings.OTEL_ENABLED:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)

        # Instrument HTTPX
        HTTPXClientInstrumentor().instrument()

        logger.info("FastAPI and HTTPX instrumented with OpenTelemetry")

    except Exception as e:
        logger.error(f"Failed to instrument app: {e}")


def get_tracer():
    """获取全局tracer"""
    return _tracer
