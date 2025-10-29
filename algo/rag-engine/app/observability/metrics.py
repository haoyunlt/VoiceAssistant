"""
Prometheus 指标定义

为 RAG Engine 提供详细的性能和质量指标
"""

import time

from prometheus_client import Counter, Gauge, Histogram, Info

# ==================== 延迟指标 ====================

rag_retrieval_latency = Histogram(
    "rag_retrieval_latency_ms",
    "RAG 检索延迟（毫秒）",
    ["strategy", "tenant_id"],  # strategy: vector/bm25/hybrid/graph
    buckets=[50, 100, 200, 500, 1000, 2000, 5000],
)

rag_rerank_latency = Histogram(
    "rag_rerank_latency_ms",
    "RAG 重排延迟（毫秒）",
    ["model", "tenant_id"],
    buckets=[10, 50, 100, 200, 500, 1000],
)

rag_e2e_latency = Histogram(
    "rag_e2e_latency_ms",
    "RAG 端到端延迟（毫秒）",
    ["mode", "tenant_id"],  # mode: simple/advanced/precise
    buckets=[500, 1000, 2000, 3000, 5000, 10000],
)

rag_llm_latency = Histogram(
    "rag_llm_latency_ms",
    "LLM 生成延迟（毫秒）",
    ["model", "tenant_id"],
    buckets=[500, 1000, 2000, 5000, 10000],
)

# ==================== 缓存指标 ====================

rag_cache_operations = Counter(
    "rag_cache_operations_total",
    "缓存操作次数",
    ["operation", "tenant_id"],  # operation: hit/miss/set
)

rag_cache_hit_ratio = Gauge(
    "rag_cache_hit_ratio",
    "缓存命中率",
    ["tenant_id"],
)

rag_cache_latency = Histogram(
    "rag_cache_latency_ms",
    "缓存查询延迟（毫秒）",
    ["operation", "tenant_id"],  # operation: get/set
    buckets=[1, 5, 10, 50, 100, 200],
)

# ==================== Token 使用指标 ====================

rag_token_usage = Counter(
    "rag_token_usage_total",
    "Token 使用总量",
    ["phase", "model", "tenant_id"],  # phase: retrieval/generation/verification
)

rag_cost_usd = Counter(
    "rag_cost_usd_total",
    "成本统计（美元）",
    ["phase", "tenant_id"],
)

# ==================== 质量指标 ====================

rag_hallucination_detected = Counter(
    "rag_hallucination_detected_total",
    "检测到幻觉次数",
    ["tenant_id"],
)

rag_self_check_triggered = Counter(
    "rag_self_check_triggered_total",
    "Self-RAG 自检触发次数",
    ["tenant_id", "result"],  # result: pass/fail/refined
)

rag_answer_length = Histogram(
    "rag_answer_length_chars",
    "答案长度（字符数）",
    ["tenant_id"],
    buckets=[100, 300, 500, 1000, 2000, 5000],
)

# ==================== 检索指标 ====================

rag_retrieved_docs_count = Histogram(
    "rag_retrieved_docs_count",
    "检索到的文档数量",
    ["strategy", "tenant_id"],
    buckets=[1, 3, 5, 10, 20, 50],
)

rag_rerank_score = Histogram(
    "rag_rerank_score",
    "重排分数分布",
    ["tenant_id"],
    buckets=[0.1, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99],
)

# ==================== 请求指标 ====================

rag_requests_total = Counter(
    "rag_requests_total",
    "RAG 请求总数",
    ["mode", "status", "tenant_id"],  # status: success/error
)

rag_errors_total = Counter(
    "rag_errors_total",
    "RAG 错误总数",
    ["error_type", "tenant_id"],
)

# ==================== 系统信息 ====================

rag_info = Info(
    "rag_engine_info",
    "RAG Engine 系统信息",
)

# ==================== 辅助函数 ====================


def record_retrieval_latency(strategy: str, tenant_id: str, latency_ms: float):
    """记录检索延迟"""
    rag_retrieval_latency.labels(strategy=strategy, tenant_id=tenant_id).observe(latency_ms)


def record_rerank_latency(model: str, tenant_id: str, latency_ms: float):
    """记录重排延迟"""
    rag_rerank_latency.labels(model=model, tenant_id=tenant_id).observe(latency_ms)


def record_e2e_latency(mode: str, tenant_id: str, latency_ms: float):
    """记录端到端延迟"""
    rag_e2e_latency.labels(mode=mode, tenant_id=tenant_id).observe(latency_ms)


def record_cache_hit(tenant_id: str):
    """记录缓存命中"""
    rag_cache_operations.labels(operation="hit", tenant_id=tenant_id).inc()


def record_cache_miss(tenant_id: str):
    """记录缓存未命中"""
    rag_cache_operations.labels(operation="miss", tenant_id=tenant_id).inc()


def record_token_usage(phase: str, model: str, tenant_id: str, tokens: int):
    """记录 Token 使用"""
    rag_token_usage.labels(phase=phase, model=model, tenant_id=tenant_id).inc(tokens)


def record_hallucination_detected(tenant_id: str):
    """记录检测到幻觉"""
    rag_hallucination_detected.labels(tenant_id=tenant_id).inc()


class RAGMetrics:
    """RAG 指标收集器（上下文管理器）"""

    def __init__(self, mode: str, tenant_id: str):
        self.mode = mode
        self.tenant_id = tenant_id
        self.start_time = None
        self.retrieval_time = 0
        self.rerank_time = 0
        self.llm_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            e2e_latency_ms = (time.time() - self.start_time) * 1000
            record_e2e_latency(self.mode, self.tenant_id, e2e_latency_ms)

            # 记录请求状态
            status = "error" if exc_type else "success"
            rag_requests_total.labels(mode=self.mode, status=status, tenant_id=self.tenant_id).inc()

            # 记录错误类型
            if exc_type:
                error_type = exc_type.__name__
                rag_errors_total.labels(error_type=error_type, tenant_id=self.tenant_id).inc()

    def record_retrieval(self, strategy: str, latency_ms: float, doc_count: int):
        """记录检索信息"""
        self.retrieval_time = latency_ms
        record_retrieval_latency(strategy, self.tenant_id, latency_ms)
        rag_retrieved_docs_count.labels(strategy=strategy, tenant_id=self.tenant_id).observe(
            doc_count
        )

    def record_rerank(self, model: str, latency_ms: float, avg_score: float):
        """记录重排信息"""
        self.rerank_time = latency_ms
        record_rerank_latency(model, self.tenant_id, latency_ms)
        if avg_score >= 0:
            rag_rerank_score.labels(tenant_id=self.tenant_id).observe(avg_score)

    def record_llm(self, model: str, latency_ms: float, tokens_used: int):
        """记录 LLM 调用信息"""
        self.llm_time = latency_ms
        rag_llm_latency.labels(model=model, tenant_id=self.tenant_id).observe(latency_ms)
        record_token_usage("generation", model, self.tenant_id, tokens_used)

    def record_answer(self, answer: str):
        """记录答案信息"""
        answer_length = len(answer)
        rag_answer_length.labels(tenant_id=self.tenant_id).observe(answer_length)


# 初始化系统信息
rag_info.info(
    {
        "version": "2.0.0",
        "service": "rag-engine",
        "features": "hybrid_retrieval,cross_encoder,semantic_cache,self_rag",
    }
)

# 导出所有指标
rag_metrics = {
    "retrieval_latency": rag_retrieval_latency,
    "rerank_latency": rag_rerank_latency,
    "e2e_latency": rag_e2e_latency,
    "cache_operations": rag_cache_operations,
    "cache_hit_ratio": rag_cache_hit_ratio,
    "token_usage": rag_token_usage,
    "cost_usd": rag_cost_usd,
    "hallucination_detected": rag_hallucination_detected,
    "requests_total": rag_requests_total,
    "errors_total": rag_errors_total,
}
