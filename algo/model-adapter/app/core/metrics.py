"""增强的Prometheus指标 - P95/P99/错误率/熔断状态."""

import logging
from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
)

logger = logging.getLogger(__name__)


# ========== 请求指标 ==========

# 请求总数
http_requests_total = Counter(
    "model_adapter_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

# 请求延迟 (P50/P95/P99)
http_request_duration_seconds = Histogram(
    "model_adapter_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 模型请求延迟
model_request_duration_seconds = Histogram(
    "model_adapter_model_request_duration_seconds",
    "Model request duration in seconds (P50/P95/P99)",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

# 请求大小 (输入token)
model_request_tokens = Histogram(
    "model_adapter_model_request_tokens",
    "Model request tokens (input)",
    ["provider", "model"],
    buckets=(10, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000),
)

# 响应大小 (输出token)
model_response_tokens = Histogram(
    "model_adapter_model_response_tokens",
    "Model response tokens (output)",
    ["provider", "model"],
    buckets=(10, 50, 100, 200, 500, 1000, 2000, 5000),
)


# ========== 错误指标 ==========

# 错误总数
model_error_total = Counter(
    "model_adapter_model_error_total",
    "Total model errors",
    ["provider", "model", "error_type"],
)

# 错误率 (通过自定义计算)
model_error_rate = Gauge(
    "model_adapter_model_error_rate",
    "Model error rate (errors per second)",
    ["provider", "model"],
)

# HTTP错误
http_errors_total = Counter(
    "model_adapter_http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "status_code"],
)


# ========== 重试与熔断指标 ==========

# 重试次数
retry_attempts_total = Counter(
    "model_adapter_retry_attempts_total",
    "Total retry attempts",
    ["provider", "reason"],
)

# 熔断器状态 (0=closed, 1=open, 2=half_open)
circuit_breaker_state = Gauge(
    "model_adapter_circuit_breaker_state",
    "Circuit breaker state",
    ["provider"],
)

# 熔断器打开次数
circuit_breaker_opened_total = Counter(
    "model_adapter_circuit_breaker_opened_total",
    "Total circuit breaker opens",
    ["provider"],
)

# 超时次数
timeout_total = Counter(
    "model_adapter_timeout_total",
    "Total timeouts",
    ["provider", "operation"],
)


# ========== 缓存指标 ==========

# 缓存命中
cache_hit_total = Counter(
    "model_adapter_cache_hit_total",
    "Total cache hits",
    ["provider", "model"],
)

# 缓存未命中
cache_miss_total = Counter(
    "model_adapter_cache_miss_total",
    "Total cache misses",
    ["provider", "model"],
)

# 缓存命中率
cache_hit_rate = Gauge(
    "model_adapter_cache_hit_rate",
    "Cache hit rate (0-1)",
    ["provider", "model"],
)

# 缓存大小
cache_size = Gauge(
    "model_adapter_cache_size",
    "Current cache size (number of entries)",
)

# 缓存操作延迟
cache_operation_duration_seconds = Histogram(
    "model_adapter_cache_operation_duration_seconds",
    "Cache operation duration",
    ["operation"],  # get/set
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


# ========== Token与成本指标 ==========

# Token使用量
tokens_used_total = Counter(
    "model_adapter_tokens_used_total",
    "Total tokens used",
    ["provider", "model", "type"],  # type: input/output
)

# 成本
cost_usd_total = Counter(
    "model_adapter_cost_usd_total",
    "Total cost in USD",
    ["provider", "model"],
)

# 每请求平均成本
cost_per_request_usd = Histogram(
    "model_adapter_cost_per_request_usd",
    "Cost per request in USD",
    ["provider", "model"],
    buckets=(0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)


# ========== 路由指标 ==========

# 路由决策
route_decision_total = Counter(
    "model_adapter_route_decision_total",
    "Total routing decisions",
    ["quality_tier", "selected_model"],
)

# 路由节省成本
route_savings_usd_total = Counter(
    "model_adapter_route_savings_usd_total",
    "Total cost savings from smart routing in USD",
)


# ========== 预算指标 ==========

# 预算使用率
budget_usage_ratio = Gauge(
    "model_adapter_budget_usage_ratio",
    "Budget usage ratio (0-1)",
    ["tenant_id"],
)

# 预算超限次数
budget_exceeded_total = Counter(
    "model_adapter_budget_exceeded_total",
    "Total budget exceeded events",
    ["tenant_id"],
)

# 自动降级次数
auto_downgrade_total = Counter(
    "model_adapter_auto_downgrade_total",
    "Total auto-downgrade events due to budget",
    ["tenant_id"],
)


# ========== 流式响应指标 ==========

# 流式响应chunks
stream_chunks_total = Counter(
    "model_adapter_stream_chunks_total",
    "Total stream chunks sent",
    ["provider", "model"],
)

# 流式错误
stream_error_total = Counter(
    "model_adapter_stream_error_total",
    "Total stream errors",
    ["provider", "error_type"],
)

# 流式延迟 (首个chunk到达时间 - TTFB)
stream_ttfb_seconds = Histogram(
    "model_adapter_stream_ttfb_seconds",
    "Time to first byte (TTFB) for streaming",
    ["provider", "model"],
    buckets=(0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0),
)


# ========== 系统指标 ==========

# 服务信息
service_info = Info(
    "model_adapter_service_info",
    "Service information",
)

# 在线provider数量
providers_available = Gauge(
    "model_adapter_providers_available",
    "Number of available providers",
)

# 活跃请求数
active_requests = Gauge(
    "model_adapter_active_requests",
    "Number of active requests",
    ["provider"],
)


# ========== 便利函数 ==========

class MetricsRecorder:
    """指标记录器."""

    @staticmethod
    def record_request(
        provider: str,
        model: str,
        duration_seconds: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool = True,
        error_type: Optional[str] = None,
    ):
        """
        记录一次模型请求的完整指标.

        Args:
            provider: 提供商
            model: 模型名称
            duration_seconds: 请求延迟(秒)
            input_tokens: 输入token数
            output_tokens: 输出token数
            cost_usd: 成本(USD)
            success: 是否成功
            error_type: 错误类型(如果失败)
        """
        # 延迟
        model_request_duration_seconds.labels(
            provider=provider,
            model=model,
        ).observe(duration_seconds)

        # Token
        model_request_tokens.labels(
            provider=provider,
            model=model,
        ).observe(input_tokens)

        model_response_tokens.labels(
            provider=provider,
            model=model,
        ).observe(output_tokens)

        tokens_used_total.labels(
            provider=provider,
            model=model,
            type="input",
        ).inc(input_tokens)

        tokens_used_total.labels(
            provider=provider,
            model=model,
            type="output",
        ).inc(output_tokens)

        # 成本
        cost_usd_total.labels(
            provider=provider,
            model=model,
        ).inc(cost_usd)

        cost_per_request_usd.labels(
            provider=provider,
            model=model,
        ).observe(cost_usd)

        # 错误
        if not success and error_type:
            model_error_total.labels(
                provider=provider,
                model=model,
                error_type=error_type,
            ).inc()

    @staticmethod
    def record_cache_hit(provider: str, model: str):
        """记录缓存命中."""
        cache_hit_total.labels(provider=provider, model=model).inc()

        # 更新命中率
        hits = cache_hit_total.labels(provider=provider, model=model)._value.get()
        misses = cache_miss_total.labels(provider=provider, model=model)._value.get()
        total = hits + misses
        if total > 0:
            hit_rate = hits / total
            cache_hit_rate.labels(provider=provider, model=model).set(hit_rate)

    @staticmethod
    def record_cache_miss(provider: str, model: str):
        """记录缓存未命中."""
        cache_miss_total.labels(provider=provider, model=model).inc()

        # 更新命中率
        hits = cache_hit_total.labels(provider=provider, model=model)._value.get()
        misses = cache_miss_total.labels(provider=provider, model=model)._value.get()
        total = hits + misses
        if total > 0:
            hit_rate = hits / total
            cache_hit_rate.labels(provider=provider, model=model).set(hit_rate)

    @staticmethod
    def update_circuit_breaker_state(provider: str, state: str):
        """
        更新熔断器状态.

        Args:
            provider: 提供商
            state: 状态 (closed/open/half-open)
        """
        state_map = {"closed": 0, "open": 1, "half-open": 2}
        state_value = state_map.get(state, -1)
        circuit_breaker_state.labels(provider=provider).set(state_value)

        if state == "open":
            circuit_breaker_opened_total.labels(provider=provider).inc()

    @staticmethod
    def set_service_info(version: str, environment: str):
        """设置服务信息."""
        service_info.info({
            "version": version,
            "environment": environment,
        })


# 导出指标
def export_metrics() -> bytes:
    """
    导出Prometheus格式的指标.

    Returns:
        指标文本(bytes)
    """
    return generate_latest()
