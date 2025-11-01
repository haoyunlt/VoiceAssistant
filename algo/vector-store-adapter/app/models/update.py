"""Vector update models"""

from typing import Any

from pydantic import BaseModel, Field


class UpdateVectorRequest(BaseModel):
    """更新向量请求"""

    backend: str = Field(default="milvus", description="后端类型", pattern="^(milvus|pgvector)$")
    chunk_id: str = Field(..., description="分块ID", min_length=1, max_length=255)
    vector: list[float] | None = Field(default=None, description="新向量（可选）")
    content: str | None = Field(default=None, description="新内容（可选）")
    metadata: dict[str, Any] | None = Field(default=None, description="新元数据（可选）")


class UpdateVectorResponse(BaseModel):
    """更新向量响应"""

    status: str = Field(..., description="状态")
    collection: str = Field(..., description="集合名称")
    backend: str = Field(..., description="后端类型")
    chunk_id: str = Field(..., description="分块ID")
    updated_fields: list[str] = Field(..., description="更新的字段列表")
    result: Any | None = Field(default=None, description="更新结果")
