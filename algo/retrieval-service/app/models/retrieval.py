"""
Retrieval data models
"""

from typing import Any

try:
    from pydantic import BaseModel, Field  # type: ignore
except ImportError:
    # Fallback for environments where pydantic is not installed
    BaseModel = dict
    Field = Any


class RetrievalDocument(BaseModel):
    """检索文档"""

    id: str = Field(..., description="文档ID")
    chunk_id: str = Field(..., description="分块ID")
    content: str = Field(..., description="文档内容")
    score: float = Field(..., description="相关性分数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    source: str | None = Field(None, description="来源（vector/bm25/hybrid）")


class VectorRequest(BaseModel):
    """向量检索请求"""

    query: str = Field(..., description="查询文本")
    query_embedding: list[float] | None = Field(
        None, description="查询向量（可选，如果提供则跳过编码）"
    )
    top_k: int | None = Field(None, description="返回的文档数量")
    tenant_id: str | None = Field(None, description="租户ID")
    filters: dict[str, Any] | None = Field(None, description="过滤条件")


class VectorResponse(BaseModel):
    """向量检索响应"""

    documents: list[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class BM25Request(BaseModel):
    """BM25检索请求"""

    query: str = Field(..., description="查询文本")
    top_k: int | None = Field(None, description="返回的文档数量")
    tenant_id: str | None = Field(None, description="租户ID")
    filters: dict[str, Any] | None = Field(None, description="过滤条件")


class BM25Response(BaseModel):
    """BM25检索响应"""

    documents: list[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class HybridRequest(BaseModel):
    """混合检索请求"""

    query: str = Field(..., description="查询文本")
    query_embedding: list[float] | None = Field(None, description="查询向量（可选）")
    top_k: int | None = Field(None, description="最终返回的文档数量")
    tenant_id: str | None = Field(None, description="租户ID")
    filters: dict[str, Any] | None = Field(None, description="过滤条件")
    enable_rerank: bool | None = Field(None, description="是否启用重排序")
    rerank_top_k: int | None = Field(None, description="重排序后返回的文档数量")
    # Query Expansion 参数 (Task 1.1)
    enable_query_expansion: bool = Field(False, description="是否启用查询扩展")
    query_expansion_max: int = Field(3, description="查询扩展最大数量")
    # Multi-Query 参数 (Task 1.2)
    enable_multi_query: bool = Field(False, description="是否启用多查询生成")
    multi_query_num: int = Field(3, description="多查询生成数量")


class HybridResponse(BaseModel):
    """混合检索响应"""

    documents: list[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    vector_count: int = Field(..., description="向量检索结果数")
    bm25_count: int = Field(..., description="BM25检索结果数")
    reranked: bool = Field(False, description="是否进行了重排序")
    latency_ms: float = Field(..., description="总延迟（毫秒）")
    # Query Expansion 信息 (Task 1.1)
    query_expanded: bool = Field(False, description="是否进行了查询扩展")
    expanded_queries: list[str] | None = Field(None, description="扩展后的查询列表")
    expansion_latency_ms: float | None = Field(None, description="查询扩展延迟（毫秒）")
    # Multi-Query 信息 (Task 1.2)
    multi_query_used: bool = Field(False, description="是否使用了多查询生成")
    generated_queries: list[str] | None = Field(None, description="生成的多查询列表")
    multi_query_latency_ms: float | None = Field(None, description="多查询生成延迟（毫秒）")


class GraphRequest(BaseModel):
    """图谱检索请求"""

    query: str = Field(..., description="查询文本")
    top_k: int | None = Field(None, description="返回的文档数量")
    depth: int | None = Field(2, ge=1, le=3, description="图谱查询深度（跳数）")
    tenant_id: str | None = Field(None, description="租户ID")


class GraphResponse(BaseModel):
    """图谱检索响应"""

    documents: list[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class HybridGraphRequest(BaseModel):
    """混合图谱检索请求（三路并行）"""

    query: str = Field(..., description="查询文本")
    query_embedding: list[float] | None = Field(None, description="查询向量（可选）")
    top_k: int | None = Field(None, description="最终返回的文档数量")
    tenant_id: str | None = Field(None, description="租户ID")
    filters: dict[str, Any] | None = Field(None, description="过滤条件")
    enable_rerank: bool | None = Field(None, description="是否启用重排序")
    rerank_top_k: int | None = Field(None, description="重排序后返回的文档数量")
    weights: dict[str, float] | None = Field(
        None,
        description="权重配置",
        example={"vector": 0.5, "bm25": 0.2, "graph": 0.3},
    )
    graph_depth: int | None = Field(2, ge=1, le=3, description="图谱查询深度（跳数）")


class HybridGraphResponse(BaseModel):
    """混合图谱检索响应（三路并行）"""

    documents: list[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    vector_count: int = Field(..., description="向量检索结果数")
    bm25_count: int = Field(..., description="BM25检索结果数")
    graph_count: int = Field(..., description="图谱检索结果数")
    reranked: bool = Field(False, description="是否进行了重排序")
    latency_ms: float = Field(..., description="总延迟（毫秒）")
    stats: dict[str, float] = Field(default_factory=dict, description="各路检索耗时统计")


# ============================================================================
# Query Enhancement Models - P2级功能
# ============================================================================


class QueryExpansionRequest(BaseModel):
    """查询扩展请求"""

    query: str = Field(..., description="原始查询")
    enable_llm: bool = Field(False, description="是否启用LLM扩展（可选，成本高）")
    max_expansions: int = Field(3, ge=1, le=10, description="最大扩展数量")
    methods: list[str] | None = Field(
        None, description="扩展方法列表 ['synonym', 'spelling', 'llm']"
    )


class QueryExpansionResponse(BaseModel):
    """查询扩展响应"""

    original: str = Field(..., description="原始查询")
    expanded: list[str] = Field(..., description="扩展后的查询列表（包含原查询）")
    weights: list[float] = Field(..., description="每个查询的权重")
    method: str = Field(..., description="使用的扩展方法")
    latency_ms: float = Field(..., description="扩展延迟（毫秒）")


class MultiQueryRequest(BaseModel):
    """多查询生成请求"""

    query: str = Field(..., description="原始查询")
    num_queries: int = Field(3, ge=1, le=10, description="生成的查询数量（不包含原查询）")


class MultiQueryResponse(BaseModel):
    """多查询生成响应"""

    original: str = Field(..., description="原始查询")
    queries: list[str] = Field(..., description="生成的查询列表（包含原查询）")
    method: str = Field(..., description="生成方法：llm/template/hybrid")
    latency_ms: float = Field(..., description="生成延迟（毫秒）")


class HyDERequest(BaseModel):
    """HyDE（假设文档嵌入）请求"""

    query: str = Field(..., description="原始查询")


class HyDEResponse(BaseModel):
    """HyDE（假设文档嵌入）响应"""

    original_query: str = Field(..., description="原始查询")
    hypothetical_document: str = Field(..., description="生成的假设性文档")
    method: str = Field(..., description="生成方法：llm/template")
    latency_ms: float = Field(..., description="生成延迟（毫秒）")
    token_count: int = Field(0, description="使用的token数")
