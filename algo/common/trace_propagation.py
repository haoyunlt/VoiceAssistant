"""
分布式追踪传播 - OpenTelemetry Context Propagation

确保跨服务调用时 trace context 正确传递。

使用方法:
  1. 在 FastAPI middleware 中使用 extract_trace_context
  2. 在 HTTP 客户端调用时使用 inject_trace_headers
"""

import logging
from typing import Any

from fastapi import Request
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import SpanKind

logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)


def extract_trace_context(request: Request) -> Any:
    """
    从 HTTP 请求头中提取 trace context

    Args:
        request: FastAPI Request 对象

    Returns:
        OpenTelemetry Context
    """
    # 从请求头提取 trace context
    carrier = dict(request.headers)
    ctx = extract(carrier)
    return ctx


def inject_trace_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """
    将当前 trace context 注入到 HTTP 请求头

    Args:
        headers: 现有请求头（可选）

    Returns:
        包含 trace 信息的请求头
    """
    if headers is None:
        headers = {}

    # 注入 trace context
    inject(headers)

    # 添加自定义 trace ID（用于日志关联）
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        trace_id = format(span.get_span_context().trace_id, "032x")
        span_id = format(span.get_span_context().span_id, "016x")

        headers["X-Trace-ID"] = trace_id
        headers["X-Span-ID"] = span_id

    return headers


async def trace_propagation_middleware(request: Request, call_next):
    """
    FastAPI 中间件：提取上游 trace context 并创建新 span

    使用方法:
        app.add_middleware(BaseHTTPMiddleware, dispatch=trace_propagation_middleware)
    """
    # 提取上游 trace context
    ctx = extract_trace_context(request)

    # 创建新 span
    with tracer.start_as_current_span(
        name=f"{request.method} {request.url.path}",
        context=ctx,
        kind=SpanKind.SERVER,
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.host": request.url.hostname,
            "http.scheme": request.url.scheme,
            "http.target": request.url.path,
        },
    ) as span:
        # 添加请求 ID
        request_id = request.headers.get("X-Request-ID")
        if request_id:
            span.set_attribute("request.id", request_id)

        # 添加租户 ID
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)

        try:
            response = await call_next(request)

            # 记录响应状态
            span.set_attribute("http.status_code", response.status_code)

            if response.status_code >= 400:
                span.set_status(trace.Status(trace.StatusCode.ERROR))

            return response

        except Exception as e:
            # 记录异常
            span.set_status(
                trace.Status(trace.StatusCode.ERROR, str(e))
            )
            span.record_exception(e)
            raise


def create_span_for_http_call(
    method: str, url: str, service_name: str
) -> trace.Span:
    """
    为 HTTP 调用创建 span

    Args:
        method: HTTP 方法
        url: 请求 URL
        service_name: 目标服务名称

    Returns:
        Span 对象
    """
    span = tracer.start_span(
        name=f"{method} {service_name}",
        kind=SpanKind.CLIENT,
        attributes={
            "http.method": method,
            "http.url": url,
            "service.name": service_name,
        },
    )
    return span
