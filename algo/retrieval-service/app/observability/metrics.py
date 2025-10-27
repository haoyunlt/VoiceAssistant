"""
Prometheus Metrics - 应用指标
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# 请求指标
request_total = Counter(
    "retrieval_requests_total",
    "Total number of retrieval requests",
    ["method", "endpoint", "status"],
)

request_duration_seconds = Histogram(
    "retrieval_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# 检索指标
retrieval_operations_total = Counter(
    "retrieval_operations_total",
    "Total number of retrieval operations",
    ["retrieval_type", "status"],
)

retrieval_duration_seconds = Histogram(
    "retrieval_duration_seconds",
    "Retrieval operation duration in seconds",
    ["retrieval_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

retrieval_results_count = Histogram(
    "retrieval_results_count",
    "Number of results returned",
    ["retrieval_type"],
    buckets=[0, 1, 5, 10, 20, 50, 100, 200],
)

# 缓存指标
cache_operations_total = Counter(
    "cache_operations_total",
    "Total number of cache operations",
    ["operation", "status"],
)

cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (hits / total)",
)

# 重排序指标
rerank_operations_total = Counter(
    "rerank_operations_total",
    "Total number of rerank operations",
    ["status"],
)

rerank_duration_seconds = Histogram(
    "rerank_duration_seconds",
    "Rerank operation duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# 熔断器指标
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
)

circuit_breaker_failures = Counter(
    "circuit_breaker_failures_total",
    "Total number of circuit breaker failures",
    ["name"],
)

# 连接池指标
connection_pool_size = Gauge(
    "connection_pool_size",
    "Connection pool size",
    ["service"],
)

connection_pool_active = Gauge(
    "connection_pool_active",
    "Active connections in pool",
    ["service"],
)

# 错误指标
errors_total = Counter(
    "retrieval_errors_total",
    "Total number of errors",
    ["error_type", "component"],
)

# 服务信息
service_info = Info(
    "retrieval_service",
    "Retrieval service information",
)


class Metrics:
    """指标收集器"""

    def __init__(self):
        self.request_total = request_total
        self.request_duration_seconds = request_duration_seconds
        self.retrieval_operations_total = retrieval_operations_total
        self.retrieval_duration_seconds = retrieval_duration_seconds
        self.retrieval_results_count = retrieval_results_count
        self.cache_operations_total = cache_operations_total
        self.cache_hit_rate = cache_hit_rate
        self.rerank_operations_total = rerank_operations_total
        self.rerank_duration_seconds = rerank_duration_seconds
        self.circuit_breaker_state = circuit_breaker_state
        self.circuit_breaker_failures = circuit_breaker_failures
        self.connection_pool_size = connection_pool_size
        self.connection_pool_active = connection_pool_active
        self.errors_total = errors_total
        self.service_info = service_info

    def record_request(self, method: str, endpoint: str, status: int, duration: float):
        """记录请求"""
        self.request_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    def record_retrieval(
        self, retrieval_type: str, duration: float, result_count: int, status: str = "success"
    ):
        """记录检索操作"""
        self.retrieval_operations_total.labels(
            retrieval_type=retrieval_type, status=status
        ).inc()
        self.retrieval_duration_seconds.labels(retrieval_type=retrieval_type).observe(
            duration
        )
        self.retrieval_results_count.labels(retrieval_type=retrieval_type).observe(
            result_count
        )

    def record_cache_operation(self, operation: str, status: str):
        """记录缓存操作"""
        self.cache_operations_total.labels(operation=operation, status=status).inc()

    def update_cache_hit_rate(self, hit_rate: float):
        """更新缓存命中率"""
        self.cache_hit_rate.set(hit_rate)

    def record_rerank(self, duration: float, status: str = "success"):
        """记录重排序操作"""
        self.rerank_operations_total.labels(status=status).inc()
        self.rerank_duration_seconds.observe(duration)

    def update_circuit_breaker_state(self, name: str, state: int):
        """更新熔断器状态"""
        self.circuit_breaker_state.labels(name=name).set(state)

    def record_circuit_breaker_failure(self, name: str):
        """记录熔断器失败"""
        self.circuit_breaker_failures.labels(name=name).inc()

    def update_connection_pool(self, service: str, size: int, active: int):
        """更新连接池指标"""
        self.connection_pool_size.labels(service=service).set(size)
        self.connection_pool_active.labels(service=service).set(active)

    def record_error(self, error_type: str, component: str):
        """记录错误"""
        self.errors_total.labels(error_type=error_type, component=component).inc()

    def set_service_info(self, info: dict):
        """设置服务信息"""
        self.service_info.info(info)


# 全局指标实例
metrics = Metrics()
