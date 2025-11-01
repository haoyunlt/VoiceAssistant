"""Batch operation models"""

from typing import Any

from pydantic import BaseModel, Field


class BatchSearchQuery(BaseModel):
    """单个批量查询"""

    query_vector: list[float] = Field(..., description="查询向量", min_length=1)
    top_k: int = Field(default=10, description="返回结果数", ge=1, le=100)
    tenant_id: str | None = Field(default=None, description="租户ID", max_length=64)
    filters: str | None = Field(default=None, description="过滤条件")
    search_params: dict[str, Any] | None = Field(default=None, description="搜索参数")


class BatchSearchRequest(BaseModel):
    """批量搜索请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")
    queries: list[BatchSearchQuery] = Field(..., description="查询列表", min_length=1, max_length=100)


class BatchSearchResult(BaseModel):
    """单个批量搜索结果"""

    results: list[dict] = Field(..., description="搜索结果")
    count: int = Field(..., description="结果数量")
    error: str | None = Field(default=None, description="错误信息（如果失败）")
    cached: bool = Field(default=False, description="是否来自缓存")


class BatchSearchResponse(BaseModel):
    """批量搜索响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    results: list[BatchSearchResult] = Field(..., description="批量结果列表")
    total_count: int = Field(..., description="总结果数")
    success_count: int = Field(..., description="成功数量")
    error_count: int = Field(..., description="失败数量")
