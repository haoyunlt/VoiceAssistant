"""
Document Domain Models

文档领域模型
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class DocumentType(str, Enum):
    """文档类型"""

    TEXT = "text"
    PDF = "pdf"
    WORD = "word"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class DocumentStatus(str, Enum):
    """文档状态"""

    UPLOADED = "uploaded"  # 已上传
    PENDING = "pending"  # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    INFECTED = "infected"  # 发现病毒
    DELETED = "deleted"  # 已删除


class Document:
    """文档聚合根"""

    def __init__(
        self,
        id: str,
        knowledge_base_id: str,
        name: str,
        file_name: str,
        file_type: DocumentType,
        file_size: int,
        file_path: str,
        tenant_id: str,
        uploaded_by: str,
        file_url: str = "",
        content: str = "",
        summary: str = "",
        status: DocumentStatus = DocumentStatus.PENDING,
        chunk_count: int = 0,
        metadata: dict[str, Any] | None = None,
        error_message: str = "",
        processed_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.knowledge_base_id = knowledge_base_id
        self.name = name
        self.file_name = file_name
        self.file_type = file_type
        self.file_size = file_size
        self.file_path = file_path
        self.file_url = file_url
        self.content = content
        self.summary = summary
        self.status = status
        self.chunk_count = chunk_count
        self.tenant_id = tenant_id
        self.uploaded_by = uploaded_by
        self.metadata = metadata or {}
        self.error_message = error_message
        self.processed_at = processed_at
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def create(
        cls,
        knowledge_base_id: str,
        name: str,
        file_name: str,
        file_type: DocumentType,
        file_size: int,
        file_path: str,
        tenant_id: str,
        uploaded_by: str,
    ) -> "Document":
        """创建新文档"""
        doc_id = f"doc_{uuid4()}"
        return cls(
            id=doc_id,
            knowledge_base_id=knowledge_base_id,
            name=name,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
        )

    def set_content(self, content: str) -> None:
        """设置文档内容"""
        self.content = content
        self.updated_at = datetime.utcnow()

    def set_summary(self, summary: str) -> None:
        """设置文档摘要"""
        self.summary = summary
        self.updated_at = datetime.utcnow()

    def set_file_url(self, url: str) -> None:
        """设置文件 URL"""
        self.file_url = url
        self.updated_at = datetime.utcnow()

    def start_processing(self) -> None:
        """开始处理"""
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def complete_processing(self, chunk_count: int) -> None:
        """完成处理"""
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def fail_processing(self, error_msg: str) -> None:
        """处理失败"""
        self.status = DocumentStatus.FAILED
        self.error_message = error_msg
        self.updated_at = datetime.utcnow()

    def mark_infected(self, virus_name: str) -> None:
        """标记为病毒文件"""
        self.status = DocumentStatus.INFECTED
        self.error_message = f"发现病毒: {virus_name}"
        self.updated_at = datetime.utcnow()

    def mark_deleted(self) -> None:
        """标记删除"""
        self.status = DocumentStatus.DELETED
        self.updated_at = datetime.utcnow()

    def update(self, name: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        """更新文档信息"""
        if name:
            self.name = name
        if metadata:
            self.metadata.update(metadata)
        self.updated_at = datetime.utcnow()

    def is_processed(self) -> bool:
        """检查是否已处理"""
        return self.status == DocumentStatus.COMPLETED

    def is_failed(self) -> bool:
        """检查是否失败"""
        return self.status == DocumentStatus.FAILED

    def is_deleted(self) -> bool:
        """检查是否已删除"""
        return self.status == DocumentStatus.DELETED

    def can_process(self) -> bool:
        """检查是否可以处理"""
        return self.status in [DocumentStatus.PENDING, DocumentStatus.FAILED]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "name": self.name,
            "file_name": self.file_name,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "file_path": self.file_path,
            "file_url": self.file_url,
            "content": self.content,
            "summary": self.summary,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "tenant_id": self.tenant_id,
            "uploaded_by": self.uploaded_by,
            "metadata": self.metadata,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Chunk:
    """文档块"""

    def __init__(
        self,
        id: str,
        document_id: str,
        knowledge_base_id: str,
        content: str,
        sequence: int,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.document_id = document_id
        self.knowledge_base_id = knowledge_base_id
        self.content = content
        self.sequence = sequence
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()

    @classmethod
    def create(
        cls,
        document_id: str,
        knowledge_base_id: str,
        content: str,
        sequence: int,
        metadata: dict[str, Any] | None = None,
    ) -> "Chunk":
        """创建新块"""
        chunk_id = f"chunk_{uuid4()}"
        return cls(
            id=chunk_id,
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            content=content,
            sequence=sequence,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "knowledge_base_id": self.knowledge_base_id,
            "content": self.content,
            "sequence": self.sequence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
