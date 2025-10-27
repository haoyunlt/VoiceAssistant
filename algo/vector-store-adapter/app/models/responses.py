"""响应模型"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="状态")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="版本")


class ReadyResponse(BaseModel):
    """就绪检查响应"""

    ready: bool = Field(..., description="是否就绪")
    checks: Optional[Dict[str, bool]] = Field(default=None, description="检查项")
    reason: Optional[str] = Field(default=None, description="未就绪原因")


class InsertResponse(BaseModel):
    """插入向量响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    inserted: int = Field(..., description="插入数量")
    result: Optional[Any] = Field(default=None, description="插入结果")


class VectorSearchResult(BaseModel):
    """向量搜索结果"""

    chunk_id: str = Field(..., description="分块ID")
    document_id: str = Field(..., description="文档ID")
    content: str = Field(..., description="内容")
    tenant_id: str = Field(..., description="租户ID")
    score: float = Field(..., description="得分")
    distance: Optional[float] = Field(default=None, description="距离")
    backend: str = Field(..., description="后端类型")


class SearchResponse(BaseModel):
    """搜索向量响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    results: List[VectorSearchResult] = Field(..., description="搜索结果")
    count: int = Field(..., description="结果数量")


class DeleteResponse(BaseModel):
    """删除响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    document_id: str = Field(..., description="文档ID")
    result: Optional[Any] = Field(default=None, description="删除结果")


class CollectionCountResponse(BaseModel):
    """集合计数响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    count: int = Field(..., description="向量数量")


class BackendStats(BaseModel):
    """后端统计"""

    initialized: bool = Field(..., description="是否已初始化")
    healthy: bool = Field(..., description="是否健康")


class StatsResponse(BaseModel):
    """统计响应"""

    backends: Dict[str, BackendStats] = Field(..., description="后端统计")
    default_backend: str = Field(..., description="默认后端")

