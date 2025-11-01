"""
Business Metrics - 业务指标监控

Prometheus指标定义，用于追踪知识服务的业务KPI
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# ============= 实体提取指标 =============

entity_extraction_total = Counter(
    "entity_extraction_total",
    "Total number of entity extraction requests",
    ["domain", "status"],  # status: success/failure
)

entity_extraction_duration = Histogram(
    "entity_extraction_duration_seconds",
    "Entity extraction duration in seconds",
    ["domain"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

entities_extracted_total = Counter(
    "entities_extracted_total",
    "Total number of entities extracted",
    ["domain", "entity_type"],
)

relations_extracted_total = Counter(
    "relations_extracted_total",
    "Total number of relations extracted",
    ["domain", "relation_type"],
)

# ============= LLM调用指标 =============

llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests",
    ["model", "operation", "status"],  # operation: extract/summarize/query
)

llm_tokens_consumed = Counter(
    "llm_tokens_consumed_total",
    "Total LLM tokens consumed",
    ["model", "operation", "token_type"],  # token_type: prompt/completion
)

llm_cost_usd = Counter(
    "llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model", "operation"],
)

llm_request_duration = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["model", "operation"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

llm_model_info = Info(
    "llm_model_info",
    "Information about LLM models in use",
)

# ============= 缓存指标 =============

cache_requests_total = Counter(
    "cache_requests_total",
    "Total cache requests",
    ["cache_type", "result"],  # result: hit/miss
)

cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (0.0-1.0)",
    ["cache_type"],  # cache_type: llm_extraction/query_entities/community_summary
)

cache_size_bytes = Gauge(
    "cache_size_bytes",
    "Cache size in bytes",
    ["cache_type"],
)

# ============= GraphRAG索引指标 =============

graphrag_index_builds_total = Counter(
    "graphrag_index_builds_total",
    "Total GraphRAG index builds",
    ["domain", "status"],
)

graphrag_index_build_duration = Histogram(
    "graphrag_index_build_duration_seconds",
    "GraphRAG index build duration in seconds",
    ["domain"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

graphrag_entities_indexed = Counter(
    "graphrag_entities_indexed_total",
    "Total entities indexed in GraphRAG",
    ["domain", "document_id"],
)

graphrag_communities_detected = Counter(
    "graphrag_communities_detected_total",
    "Total communities detected",
    ["domain", "document_id"],
)

graphrag_index_size = Gauge(
    "graphrag_index_size",
    "Current GraphRAG index size (number of entities)",
    ["domain"],
)

# ============= 检索指标 =============

retrieval_requests_total = Counter(
    "retrieval_requests_total",
    "Total retrieval requests",
    ["mode", "status"],  # mode: vector/graph/bm25/hybrid
)

retrieval_duration = Histogram(
    "retrieval_duration_seconds",
    "Retrieval duration in seconds",
    ["mode"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0],
)

retrieval_results_count = Histogram(
    "retrieval_results_count",
    "Number of results returned",
    ["mode"],
    buckets=[1, 5, 10, 20, 50, 100],
)

retrieval_recall_at_k = Gauge(
    "retrieval_recall_at_k",
    "Retrieval recall@k on test set",
    ["mode", "k"],  # k: 5/10/20
)

# ============= 社区检测指标 =============

community_detection_total = Counter(
    "community_detection_total",
    "Total community detection runs",
    ["algorithm", "status"],  # algorithm: louvain/connected_components
)

community_detection_duration = Histogram(
    "community_detection_duration_seconds",
    "Community detection duration",
    ["algorithm"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
)

community_modularity = Gauge(
    "community_modularity",
    "Community modularity score",
    ["document_id", "algorithm"],
)

# ============= 实体链接指标 =============

entity_linking_total = Counter(
    "entity_linking_total",
    "Total entity linking operations",
    ["status"],
)

entities_merged_total = Counter(
    "entities_merged_total",
    "Total entities merged",
    ["method"],  # method: text_similarity/embedding_similarity
)

entity_linking_precision = Gauge(
    "entity_linking_precision",
    "Entity linking precision on test set",
    ["method"],
)

# ============= 增量索引指标 =============

incremental_updates_total = Counter(
    "incremental_updates_total",
    "Total incremental index updates",
    ["change_type", "status"],  # change_type: create/update/delete
)

incremental_update_duration = Histogram(
    "incremental_update_duration_seconds",
    "Incremental update duration",
    ["change_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# ============= 图数据库指标 =============

neo4j_nodes_total = Gauge(
    "neo4j_nodes_total",
    "Total nodes in Neo4j",
    ["label"],
)

neo4j_relationships_total = Gauge(
    "neo4j_relationships_total",
    "Total relationships in Neo4j",
    ["type"],
)

neo4j_query_duration = Histogram(
    "neo4j_query_duration_seconds",
    "Neo4j query duration",
    ["query_type"],  # query_type: read/write
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
)

# ============= 错误与降级指标 =============

errors_total = Counter(
    "errors_total",
    "Total errors by type",
    ["error_type", "component"],
)

fallback_triggered_total = Counter(
    "fallback_triggered_total",
    "Total fallback triggers",
    ["component", "fallback_type"],
)

service_degraded = Gauge(
    "service_degraded",
    "Service degradation status (0=normal, 1=degraded)",
    ["component"],
)


# ============= 辅助函数 =============


def record_entity_extraction(
    domain: str,
    duration: float,
    entity_count: int,
    relation_count: int,
    success: bool = True,
):
    """记录实体提取指标"""
    status = "success" if success else "failure"
    entity_extraction_total.labels(domain=domain, status=status).inc()
    entity_extraction_duration.labels(domain=domain).observe(duration)

    if success:
        entities_extracted_total.labels(domain=domain, entity_type="all").inc(entity_count)
        relations_extracted_total.labels(domain=domain, relation_type="all").inc(relation_count)


def record_llm_call(
    model: str,
    operation: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float,
    duration: float,
    success: bool = True,
):
    """记录LLM调用指标"""
    status = "success" if success else "failure"
    llm_requests_total.labels(model=model, operation=operation, status=status).inc()

    if success:
        llm_tokens_consumed.labels(model=model, operation=operation, token_type="prompt").inc(
            prompt_tokens
        )
        llm_tokens_consumed.labels(model=model, operation=operation, token_type="completion").inc(
            completion_tokens
        )
        llm_cost_usd.labels(model=model, operation=operation).inc(cost)
        llm_request_duration.labels(model=model, operation=operation).observe(duration)


def record_cache_access(cache_type: str, hit: bool):
    """记录缓存访问"""
    result = "hit" if hit else "miss"
    cache_requests_total.labels(cache_type=cache_type, result=result).inc()


def record_retrieval(mode: str, duration: float, result_count: int, success: bool = True):
    """记录检索请求"""
    status = "success" if success else "failure"
    retrieval_requests_total.labels(mode=mode, status=status).inc()

    if success:
        retrieval_duration.labels(mode=mode).observe(duration)
        retrieval_results_count.labels(mode=mode).observe(result_count)


def record_fallback(component: str, fallback_type: str):
    """记录降级事件"""
    fallback_triggered_total.labels(component=component, fallback_type=fallback_type).inc()
    service_degraded.labels(component=component).set(1)
