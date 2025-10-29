"""
Database Models

SQLAlchemy 数据库模型定义
"""

import json
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text, Index, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class DocumentModel(Base):
    """文档表"""

    __tablename__ = "documents"

    id = Column(String(100), primary_key=True)
    knowledge_base_id = Column(String(100), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_url = Column(String(1000))
    content = Column(Text)
    summary = Column(Text)
    status = Column(String(50), nullable=False, index=True)
    chunk_count = Column(Integer, default=0)
    tenant_id = Column(String(100), nullable=False, index=True)
    uploaded_by = Column(String(100), nullable=False)
    metadata = Column(JSON, default=dict)
    error_message = Column(Text)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_documents_tenant_kb', 'tenant_id', 'knowledge_base_id'),
        Index('idx_documents_status', 'status'),
        Index('idx_documents_created_at', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "name": self.name,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "file_path": self.file_path,
            "file_url": self.file_url,
            "content": self.content,
            "summary": self.summary,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "tenant_id": self.tenant_id,
            "uploaded_by": self.uploaded_by,
            "metadata": self.metadata or {},
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class ChunkModel(Base):
    """文档块表"""

    __tablename__ = "chunks"

    id = Column(String(100), primary_key=True)
    document_id = Column(String(100), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True)
    knowledge_base_id = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sequence = Column(Integer, nullable=False)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_chunks_document', 'document_id', 'sequence'),
        Index('idx_chunks_kb', 'knowledge_base_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "knowledge_base_id": self.knowledge_base_id,
            "content": self.content,
            "sequence": self.sequence,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat()
        }


class VersionModel(Base):
    """版本表"""

    __tablename__ = "versions"

    id = Column(String(100), primary_key=True)
    knowledge_base_id = Column(String(100), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    description = Column(Text)
    created_by = Column(String(100), nullable=False)
    tenant_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Unique constraint
    __table_args__ = (
        Index('idx_versions_kb_version', 'knowledge_base_id', 'version', unique=True),
        Index('idx_versions_tenant', 'tenant_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "knowledge_base_id": self.knowledge_base_id,
            "version": self.version,
            "snapshot": self.snapshot,
            "description": self.description,
            "created_by": self.created_by,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat()
        }


class RoleModel(Base):
    """角色表"""

    __tablename__ = "roles"

    id = Column(String(100), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    permissions = Column(JSON, nullable=False)
    tenant_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_roles_tenant_name', 'tenant_id', 'name', unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": self.permissions,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class UserRoleModel(Base):
    """用户角色关联表"""

    __tablename__ = "user_roles"

    id = Column(String(100), primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    role_id = Column(String(100), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    tenant_id = Column(String(100), nullable=False, index=True)
    resource = Column(String(200))  # 可选：限定资源范围
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime)

    # Relationship
    role = relationship("RoleModel")

    # Indexes
    __table_args__ = (
        Index('idx_user_roles_user_tenant', 'user_id', 'tenant_id'),
        Index('idx_user_roles_role', 'role_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "tenant_id": self.tenant_id,
            "resource": self.resource,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class AuditLogModel(Base):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id = Column(String(100), primary_key=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(200))
    details = Column(Text)
    ip = Column(String(45))
    user_agent = Column(String(500))
    status = Column(String(20), nullable=False)
    error = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_tenant_user_time', 'tenant_id', 'user_id', 'created_at'),
        Index('idx_audit_logs_action_time', 'action', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat()
        }
