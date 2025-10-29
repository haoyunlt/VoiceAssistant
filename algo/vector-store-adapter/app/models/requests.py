"""请求模型"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class VectorData(BaseModel):
    """向量数据"""

    chunk_id: str = Field(..., description="分块ID", min_length=1, max_length=128)
    document_id: str = Field(..., description="文档ID", min_length=1, max_length=64)
    content: str = Field(..., description="内容", min_length=1)
    embedding: list[float] = Field(..., description="向量", min_length=1)
    tenant_id: str = Field(default="default", description="租户ID", max_length=64)
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: list[float]) -> list[float]:
        """验证向量维度"""
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("embedding must contain only numbers")
        return v


class InsertVectorsRequest(BaseModel):
    """插入向量请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")
    data: VectorData | list[VectorData] = Field(..., description="向量数据（单条或列表）")

    @field_validator("data")
    @classmethod
    def ensure_list(cls, v: VectorData | list[VectorData]) -> list[VectorData]:
        """确保数据是列表"""
        if isinstance(v, VectorData):
            return [v]
        return v


class SearchVectorsRequest(BaseModel):
    """搜索向量请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")
    query_vector: list[float] = Field(..., description="查询向量", min_length=1)
    top_k: int = Field(default=10, description="返回结果数", ge=1, le=100)
    tenant_id: str | None = Field(default=None, description="租户ID（用于过滤）", max_length=64)
    filters: str | None = Field(default=None, description="额外过滤条件")
    search_params: dict[str, Any] | None = Field(default=None, description="搜索参数")

    @field_validator("query_vector")
    @classmethod
    def validate_query_vector(cls, v: list[float]) -> list[float]:
        """验证查询向量"""
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("query_vector must contain only numbers")
        return v


class DeleteByDocumentRequest(BaseModel):
    """删除文档请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")

