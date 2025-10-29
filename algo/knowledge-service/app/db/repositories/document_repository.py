"""
Document Repository

文档数据访问层
"""

import logging
from typing import List, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChunkModel, DocumentModel
from app.models.document import Chunk, Document, DocumentStatus, DocumentType

logger = logging.getLogger(__name__)


class DocumentRepository:
    """文档仓库"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        """创建文档

        Args:
            document: 文档对象

        Returns:
            创建的文档
        """
        model = DocumentModel(
            id=document.id,
            knowledge_base_id=document.knowledge_base_id,
            name=document.name,
            file_name=document.file_name,
            file_type=document.file_type.value,
            file_size=document.file_size,
            file_path=document.file_path,
            file_url=document.file_url,
            content=document.content,
            summary=document.summary,
            status=document.status.value,
            chunk_count=document.chunk_count,
            tenant_id=document.tenant_id,
            uploaded_by=document.uploaded_by,
            metadata=document.metadata,
            error_message=document.error_message,
            processed_at=document.processed_at,
            created_at=document.created_at,
            updated_at=document.updated_at
        )

        self.session.add(model)
        await self.session.flush()

        logger.info(f"Created document: {document.id}")
        return document

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """根据 ID 获取文档

        Args:
            document_id: 文档 ID

        Returns:
            文档对象或 None
        """
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._model_to_entity(model)

    async def list_by_knowledge_base(
        self,
        knowledge_base_id: str,
        tenant_id: str,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None
    ) -> tuple[List[Document], int]:
        """列出知识库的文档

        Args:
            knowledge_base_id: 知识库 ID
            tenant_id: 租户 ID
            offset: 偏移量
            limit: 数量限制
            status: 状态过滤（可选）

        Returns:
            (文档列表, 总数)
        """
        # 构建查询条件
        conditions = [
            DocumentModel.knowledge_base_id == knowledge_base_id,
            DocumentModel.tenant_id == tenant_id
        ]

        if status:
            conditions.append(DocumentModel.status == status)

        # 查询总数
        count_result = await self.session.execute(
            select(DocumentModel).where(and_(*conditions))
        )
        total = len(count_result.all())

        # 查询数据
        result = await self.session.execute(
            select(DocumentModel)
            .where(and_(*conditions))
            .order_by(desc(DocumentModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        models = result.scalars().all()

        documents = [self._model_to_entity(model) for model in models]

        return documents, total

    async def update(self, document: Document) -> Document:
        """更新文档

        Args:
            document: 文档对象

        Returns:
            更新后的文档
        """
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document.id)
        )
        model = result.scalar_one_or_none()

        if not model:
            raise ValueError(f"Document not found: {document.id}")

        # 更新字段
        model.name = document.name
        model.file_url = document.file_url
        model.content = document.content
        model.summary = document.summary
        model.status = document.status.value
        model.chunk_count = document.chunk_count
        model.metadata = document.metadata
        model.error_message = document.error_message
        model.processed_at = document.processed_at
        model.updated_at = document.updated_at

        await self.session.flush()

        logger.info(f"Updated document: {document.id}")
        return document

    async def delete(self, document_id: str) -> bool:
        """删除文档

        Args:
            document_id: 文档 ID

        Returns:
            是否成功
        """
        result = await self.session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self.session.delete(model)
        await self.session.flush()

        logger.info(f"Deleted document: {document_id}")
        return True

    async def create_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """批量创建文档块

        Args:
            chunks: 文档块列表

        Returns:
            创建的文档块列表
        """
        models = [
            ChunkModel(
                id=chunk.id,
                document_id=chunk.document_id,
                knowledge_base_id=chunk.knowledge_base_id,
                content=chunk.content,
                sequence=chunk.sequence,
                metadata=chunk.metadata,
                created_at=chunk.created_at
            )
            for chunk in chunks
        ]

        self.session.add_all(models)
        await self.session.flush()

        logger.info(f"Created {len(chunks)} chunks")
        return chunks

    async def get_chunks_by_document(self, document_id: str) -> List[Chunk]:
        """获取文档的所有块

        Args:
            document_id: 文档 ID

        Returns:
            文档块列表
        """
        result = await self.session.execute(
            select(ChunkModel)
            .where(ChunkModel.document_id == document_id)
            .order_by(ChunkModel.sequence)
        )
        models = result.scalars().all()

        return [self._chunk_model_to_entity(model) for model in models]

    def _model_to_entity(self, model: DocumentModel) -> Document:
        """将模型转换为实体

        Args:
            model: 数据库模型

        Returns:
            文档实体
        """
        return Document(
            id=model.id,
            knowledge_base_id=model.knowledge_base_id,
            name=model.name,
            file_name=model.file_name,
            file_type=DocumentType(model.file_type),
            file_size=model.file_size,
            file_path=model.file_path,
            file_url=model.file_url or "",
            content=model.content or "",
            summary=model.summary or "",
            status=DocumentStatus(model.status),
            chunk_count=model.chunk_count,
            tenant_id=model.tenant_id,
            uploaded_by=model.uploaded_by,
            metadata=model.metadata or {},
            error_message=model.error_message or "",
            processed_at=model.processed_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _chunk_model_to_entity(self, model: ChunkModel) -> Chunk:
        """将模型转换为实体

        Args:
            model: 数据库模型

        Returns:
            块实体
        """
        return Chunk(
            id=model.id,
            document_id=model.document_id,
            knowledge_base_id=model.knowledge_base_id,
            content=model.content,
            sequence=model.sequence,
            metadata=model.metadata or {},
            created_at=model.created_at
        )
