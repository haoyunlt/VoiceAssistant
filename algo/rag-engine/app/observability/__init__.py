"""
RAG Engine 可观测性模块

提供 Prometheus 指标和 OpenTelemetry 追踪
"""

from app.observability.metrics import (
    rag_metrics,
    record_cache_hit,
    record_cache_miss,
    record_e2e_latency,
    record_hallucination_detected,
    record_rerank_latency,
    record_retrieval_latency,
    record_token_usage,
)

__all__ = [
    "rag_metrics",
    "record_retrieval_latency",
    "record_rerank_latency",
    "record_e2e_latency",
    "record_cache_hit",
    "record_cache_miss",
    "record_token_usage",
    "record_hallucination_detected",
]
