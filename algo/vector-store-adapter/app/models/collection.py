"""Collection management models"""

from typing import Any

from pydantic import BaseModel, Field


class CollectionInfo(BaseModel):
    """集合信息"""

    name: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    count: int = Field(..., description="向量数量")
    dimension: int | None = Field(default=None, description="向量维度")


class CollectionListResponse(BaseModel):
    """集合列表响应"""

    status: str = Field(..., description="状态")
    collections: list[CollectionInfo] = Field(..., description="集合列表")
    total: int = Field(..., description="总数")


class CollectionSchemaField(BaseModel):
    """集合字段定义"""

    name: str = Field(..., description="字段名")
    type: str = Field(..., description="字段类型")
    description: str | None = Field(default=None, description="字段描述")


class CollectionSchemaResponse(BaseModel):
    """集合Schema响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    fields: list[CollectionSchemaField] = Field(..., description="字段列表")


class CollectionStatsResponse(BaseModel):
    """集合统计响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    count: int = Field(..., description="向量数量")
    dimension: int | None = Field(default=None, description="向量维度")
    stats: dict[str, Any] = Field(default_factory=dict, description="扩展统计信息")
