"""
Retrieval data models
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RetrievalDocument(BaseModel):
    """检索文档"""

    id: str = Field(..., description="文档ID")
    chunk_id: str = Field(..., description="分块ID")
    content: str = Field(..., description="文档内容")
    score: float = Field(..., description="相关性分数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    source: Optional[str] = Field(None, description="来源（vector/bm25/hybrid）")


class VectorRequest(BaseModel):
    """向量检索请求"""

    query: str = Field(..., description="查询文本")
    query_embedding: Optional[List[float]] = Field(None, description="查询向量（可选，如果提供则跳过编码）")
    top_k: Optional[int] = Field(None, description="返回的文档数量")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")


class VectorResponse(BaseModel):
    """向量检索响应"""

    documents: List[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class BM25Request(BaseModel):
    """BM25检索请求"""

    query: str = Field(..., description="查询文本")
    top_k: Optional[int] = Field(None, description="返回的文档数量")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")


class BM25Response(BaseModel):
    """BM25检索响应"""

    documents: List[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class HybridRequest(BaseModel):
    """混合检索请求"""

    query: str = Field(..., description="查询文本")
    query_embedding: Optional[List[float]] = Field(None, description="查询向量（可选）")
    top_k: Optional[int] = Field(None, description="最终返回的文档数量")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    enable_rerank: Optional[bool] = Field(None, description="是否启用重排序")
    rerank_top_k: Optional[int] = Field(None, description="重排序后返回的文档数量")


class HybridResponse(BaseModel):
    """混合检索响应"""

    documents: List[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    vector_count: int = Field(..., description="向量检索结果数")
    bm25_count: int = Field(..., description="BM25检索结果数")
    reranked: bool = Field(False, description="是否进行了重排序")
    latency_ms: float = Field(..., description="总延迟（毫秒）")


class GraphRequest(BaseModel):
    """图谱检索请求"""

    query: str = Field(..., description="查询文本")
    top_k: Optional[int] = Field(None, description="返回的文档数量")
    depth: Optional[int] = Field(2, ge=1, le=3, description="图谱查询深度（跳数）")
    tenant_id: Optional[str] = Field(None, description="租户ID")


class GraphResponse(BaseModel):
    """图谱检索响应"""

    documents: List[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    latency_ms: float = Field(..., description="检索延迟（毫秒）")


class HybridGraphRequest(BaseModel):
    """混合图谱检索请求（三路并行）"""

    query: str = Field(..., description="查询文本")
    query_embedding: Optional[List[float]] = Field(None, description="查询向量（可选）")
    top_k: Optional[int] = Field(None, description="最终返回的文档数量")
    tenant_id: Optional[str] = Field(None, description="租户ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    enable_rerank: Optional[bool] = Field(None, description="是否启用重排序")
    rerank_top_k: Optional[int] = Field(None, description="重排序后返回的文档数量")
    weights: Optional[Dict[str, float]] = Field(
        None,
        description="权重配置",
        example={"vector": 0.5, "bm25": 0.2, "graph": 0.3},
    )
    graph_depth: Optional[int] = Field(2, ge=1, le=3, description="图谱查询深度（跳数）")


class HybridGraphResponse(BaseModel):
    """混合图谱检索响应（三路并行）"""

    documents: List[RetrievalDocument] = Field(default_factory=list, description="检索到的文档")
    query: str = Field(..., description="查询文本")
    vector_count: int = Field(..., description="向量检索结果数")
    bm25_count: int = Field(..., description="BM25检索结果数")
    graph_count: int = Field(..., description="图谱检索结果数")
    reranked: bool = Field(False, description="是否进行了重排序")
    latency_ms: float = Field(..., description="总延迟（毫秒）")
    stats: Dict[str, float] = Field(default_factory=dict, description="各路检索耗时统计")
