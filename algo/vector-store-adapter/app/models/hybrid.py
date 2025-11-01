"""Hybrid search models"""

from typing import Any

from pydantic import BaseModel, Field


class HybridSearchRequest(BaseModel):
    """混合检索请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")
    query_vector: list[float] = Field(..., description="查询向量", min_length=1)
    query_text: str = Field(..., description="查询文本（用于 BM25）", min_length=1)
    top_k: int = Field(default=10, description="返回结果数", ge=1, le=100)
    tenant_id: str | None = Field(default=None, description="租户ID", max_length=64)
    filters: str | None = Field(default=None, description="过滤条件")
    search_params: dict[str, Any] | None = Field(default=None, description="搜索参数")

    # Fusion parameters
    fusion_method: str = Field(
        default="rrf",
        description="融合方法: rrf (Reciprocal Rank Fusion) 或 weighted",
        pattern="^(rrf|weighted)$",
    )
    vector_weight: float = Field(
        default=0.5,
        description="向量检索权重 (0-1)，RRF 和 weighted 都使用",
        ge=0.0,
        le=1.0,
    )
    rrf_k: int = Field(
        default=60,
        description="RRF 常数 k",
        ge=1,
    )


class HybridSearchResponse(BaseModel):
    """混合检索响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    results: list[dict] = Field(..., description="混合检索结果")
    count: int = Field(..., description="结果数量")
    fusion_method: str = Field(..., description="融合方法")
    vector_weight: float = Field(..., description="向量权重")
    cached: bool = Field(default=False, description="是否来自缓存")
