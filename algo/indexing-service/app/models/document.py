"""文档相关数据模型"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """文档状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentFormat(str, Enum):
    """文档格式"""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "md"
    HTML = "html"
    JSON = "json"


class Document(BaseModel):
    """文档模型"""

    id: str
    name: str
    format: DocumentFormat
    size: int  # bytes
    content: str | None = None
    storage_path: str
    tenant_id: str
    user_id: str
    knowledge_base_id: str
    status: DocumentStatus = DocumentStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    indexed_at: datetime | None = None


class Chunk(BaseModel):
    """文本块模型"""

    id: str
    document_id: str
    content: str
    position: int  # 在文档中的位置
    chunk_size: int
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IndexingJob(BaseModel):
    """索引任务模型"""

    job_id: str
    document_id: str
    status: DocumentStatus
    chunks_count: int = 0
    vectors_count: int = 0
    graph_nodes_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexingResult(BaseModel):
    """索引结果"""

    document_id: str
    status: DocumentStatus
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    vectors_inserted: int = 0
    graph_nodes_created: int = 0
    processing_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
