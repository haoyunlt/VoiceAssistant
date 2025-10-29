"""
Metrics Middleware - Prometheus 指标中间件
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response  # type: ignore[import]
from prometheus_client import Counter, Gauge, Histogram  # type: ignore[import]
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore[import]

# HTTP Metrics
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress", "HTTP requests currently in progress", ["method", "endpoint"]
)

# LLM Metrics
llm_request_total = Counter("llm_request_total", "Total LLM requests", ["vendor", "model"])

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["vendor", "model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

llm_token_usage = Counter(
    "llm_token_usage",
    "Total LLM tokens used",
    ["vendor", "model", "type"],  # token type: prompt or completion
)

llm_error_total = Counter("llm_error_total", "Total LLM errors", ["vendor", "model", "error_type"])

# WebSocket Metrics
websocket_connections_active = Gauge("websocket_connections_active", "Active WebSocket connections")

websocket_messages_total = Counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    ["direction"],  # sent, received
)

websocket_connection_duration_seconds = Histogram(
    "websocket_connection_duration_seconds",
    "WebSocket connection duration in seconds",
    buckets=(1, 5, 10, 30, 60, 300, 600, 1800, 3600),
)

# Agent Metrics
agent_execution_total = Counter(
    "agent_execution_total",
    "Total agent executions",
    ["mode", "status"],  # mode: react/plan_execute, status: success/failure
)

agent_execution_duration_seconds = Histogram(
    "agent_execution_duration_seconds",
    "Agent execution duration in seconds",
    ["mode"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0),
)

agent_tool_calls_total = Counter(
    "agent_tool_calls_total", "Total agent tool calls", ["tool_name", "status"]
)

# Memory Metrics
memory_operations_total = Counter(
    "memory_operations_total",
    "Total memory operations",
    ["operation"],  # store, retrieve, search
)

memory_operation_duration_seconds = Histogram(
    "memory_operation_duration_seconds",
    "Memory operation duration in seconds",
    ["operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标中间件"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path

        # Track in-progress requests
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Track request duration
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

        return response
