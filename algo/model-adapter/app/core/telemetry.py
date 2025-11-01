"""增强的OpenTelemetry支持 - 完整Span + Context传播."""

import logging
from contextvars import ContextVar
from typing import Any, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

# 全局Tracer
tracer = trace.get_tracer(__name__)

# Context变量 (用于传递租户ID等)
current_tenant_id: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
current_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def init_telemetry(
    service_name: str = "model-adapter",
    service_version: str = "1.0.0",
    environment: str = "development",
    otlp_endpoint: Optional[str] = None,
    enabled: bool = True,
) -> TracerProvider:
    """
    初始化OpenTelemetry.

    Args:
        service_name: 服务名称
        service_version: 服务版本
        environment: 环境
        otlp_endpoint: OTLP Collector endpoint
        enabled: 是否启用

    Returns:
        TracerProvider实例
    """
    if not enabled:
        logger.info("OpenTelemetry disabled")
        return None

    # 创建Resource (包含服务信息)
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": environment,
        }
    )

    # 创建TracerProvider
    provider = TracerProvider(resource=resource)

    # 配置Exporter
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)
        logger.info(f"OpenTelemetry exporter configured: {otlp_endpoint}")
    else:
        logger.info("OpenTelemetry enabled without exporter (local only)")

    # 设置全局TracerProvider
    trace.set_tracer_provider(provider)

    # 自动instrumentation
    FastAPIInstrumentor.instrument()
    HTTPXClientInstrumentor.instrument()

    logger.info(
        f"OpenTelemetry initialized: service={service_name}, "
        f"version={service_version}, env={environment}"
    )

    return provider


def add_span_attributes(**kwargs):
    """
    向当前Span添加属性.

    Example:
        add_span_attributes(
            provider="openai",
            model="gpt-4",
            tokens=1234,
        )
    """
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in kwargs.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[dict] = None):
    """
    向当前Span添加事件.

    Args:
        name: 事件名称
        attributes: 事件属性
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes=attributes or {})


def start_span(
    name: str,
    attributes: Optional[dict] = None,
) -> trace.Span:
    """
    启动一个新的Span.

    Args:
        name: Span名称
        attributes: Span属性

    Returns:
        Span实例

    Example:
        with start_span("openai.generate", {"model": "gpt-4"}):
            ...
    """
    span = tracer.start_span(name)

    if span.is_recording() and attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)

    return span


def trace_adapter_generate(provider: str, model: str):
    """
    装饰器: 追踪Adapter的generate方法.

    Args:
        provider: 提供商名称
        model: 模型名称

    Example:
        @trace_adapter_generate("openai", "gpt-4")
        async def generate(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                f"{provider}.generate",
                attributes={
                    "provider": provider,
                    "model": model,
                    "operation": "generate",
                },
            ) as span:
                try:
                    # 添加请求参数
                    if "temperature" in kwargs:
                        span.set_attribute("temperature", kwargs["temperature"])
                    if "max_tokens" in kwargs:
                        span.set_attribute("max_tokens", kwargs["max_tokens"])

                    # 添加Context变量
                    tenant_id = current_tenant_id.get()
                    if tenant_id:
                        span.set_attribute("tenant.id", tenant_id)

                    request_id = current_request_id.get()
                    if request_id:
                        span.set_attribute("request.id", request_id)

                    # 执行函数
                    result = await func(*args, **kwargs)

                    # 添加响应信息
                    if hasattr(result, "usage"):
                        usage = result.usage
                        span.set_attribute("tokens.prompt", usage.get("prompt_tokens", 0))
                        span.set_attribute("tokens.completion", usage.get("completion_tokens", 0))
                        span.set_attribute("tokens.total", usage.get("total_tokens", 0))

                    span.set_status(trace.Status(trace.StatusCode.OK))

                    return result

                except Exception as e:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def trace_cache_operation(operation: str):
    """
    装饰器: 追踪缓存操作.

    Args:
        operation: 操作类型 (get/set)

    Example:
        @trace_cache_operation("get")
        async def get_cached(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                f"cache.{operation}",
                attributes={"cache.operation": operation},
            ) as span:
                try:
                    result = await func(*args, **kwargs)

                    # 记录缓存命中/未命中
                    if operation == "get":
                        hit = result is not None
                        span.set_attribute("cache.hit", hit)

                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result

                except Exception as e:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def trace_routing_decision():
    """
    装饰器: 追踪路由决策.

    Example:
        @trace_routing_decision()
        def route(...):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(
                "smart_router.route",
                attributes={"router.operation": "route"},
            ) as span:
                try:
                    result = func(*args, **kwargs)

                    # 记录路由结果
                    if hasattr(result, "provider"):
                        span.set_attribute("route.provider", result.provider)
                    if hasattr(result, "model"):
                        span.set_attribute("route.model", result.model)
                    if hasattr(result, "quality_tier"):
                        span.set_attribute("route.quality_tier", result.quality_tier)
                    if hasattr(result, "estimated_cost"):
                        span.set_attribute("route.estimated_cost", result.estimated_cost)

                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result

                except Exception as e:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


# Context传播
propagator = TraceContextTextMapPropagator()


def inject_trace_context(carrier: dict):
    """
    注入Trace Context到carrier.

    Args:
        carrier: 载体 (如HTTP headers)

    Example:
        headers = {}
        inject_trace_context(headers)
        # headers现在包含Trace Context
    """
    propagator.inject(carrier)


def extract_trace_context(carrier: dict):
    """
    从carrier提取Trace Context.

    Args:
        carrier: 载体 (如HTTP headers)

    Example:
        extract_trace_context(request.headers)
        # 现在Context已经传播到当前Span
    """
    context = propagator.extract(carrier)
    trace.set_span_in_context(trace.get_current_span(), context)


# 便利函数
def get_trace_id() -> str:
    """获取当前Trace ID."""
    span = trace.get_current_span()
    if span:
        trace_id = span.get_span_context().trace_id
        return format(trace_id, '032x')  # 32位hex字符串
    return ""


def get_span_id() -> str:
    """获取当前Span ID."""
    span = trace.get_current_span()
    if span:
        span_id = span.get_span_context().span_id
        return format(span_id, '016x')  # 16位hex字符串
    return ""
