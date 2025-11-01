"""文档处理服务"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.models.document import DocumentStatus
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.parser_service import ParserService
from app.services.storage_service import StorageService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class DocumentService:
    """文档处理服务"""

    def __init__(self):
        self.parser_service = ParserService()
        self.chunk_service = ChunkService()
        self.embedding_service = EmbeddingService()
        self.vector_service = VectorService()
        self.storage_service = StorageService()
        self.jobs: dict[str, dict[str, Any]] = {}  # 简单内存存储

    async def save_document(
        self,
        filename: str,
        content: bytes,
        tenant_id: str,
        knowledge_base_id: str,
    ) -> dict[str, Any]:
        """
        保存文档到对象存储

        Args:
            filename: 文件名
            content: 文件内容（字节）
            tenant_id: 租户ID
            knowledge_base_id: 知识库ID

        Returns:
            文档信息
        """
        try:
            document_id = f"doc_{uuid.uuid4().hex[:16]}"

            # 上传到MinIO
            storage_path = await self.storage_service.upload(
                document_id=document_id,
                filename=filename,
                content=content,
            )

            # 创建文档记录
            document = {
                "id": document_id,
                "name": filename,
                "format": filename.split(".")[-1].lower(),
                "size": len(content),
                "storage_path": storage_path,
                "tenant_id": tenant_id,
                "knowledge_base_id": knowledge_base_id,
                "status": DocumentStatus.PENDING,
                "created_at": datetime.utcnow().isoformat(),
            }

            logger.info(f"Document saved: {document_id}")
            return document

        except Exception as e:
            logger.error(f"Failed to save document: {e}", exc_info=True)
            raise

    async def create_indexing_job(
        self,
        document_id: str,
        tenant_id: str,
        knowledge_base_id: str,
        options: dict[str, Any],
    ) -> str:
        """创建索引任务"""
        job_id = f"job_{uuid.uuid4().hex[:16]}"

        self.jobs[job_id] = {
            "job_id": job_id,
            "document_id": document_id,
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "status": DocumentStatus.PENDING,
            "options": options,
            "created_at": datetime.utcnow().isoformat(),
        }

        return job_id

    async def process_document(
        self,
        document_id: str,
        job_id: str,
        options: dict[str, Any],
    ):
        """
        处理文档（完整流程）

        流程:
        1. 解析文档内容
        2. 文本分块
        3. 向量化
        4. 存储到Milvus
        5. 构建知识图谱（可选）
        """
        start_time = time.time()

        try:
            # 更新状态
            self.jobs[job_id]["status"] = DocumentStatus.PROCESSING
            self.jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

            logger.info(f"[{job_id}] Starting document processing: {document_id}")

            # 1. 下载文档内容
            content = await self.storage_service.download(document_id)
            logger.info(f"[{job_id}] Document downloaded")

            # 2. 解析文档
            parsed_content = await self.parser_service.parse(
                content=content,
                format=options.get("format", "txt"),
            )
            logger.info(f"[{job_id}] Document parsed, length: {len(parsed_content)}")

            # 3. 文本分块
            chunks = await self.chunk_service.create_chunks(
                document_id=document_id,
                content=parsed_content,
                chunk_size=options.get("chunk_size", settings.MAX_CHUNK_SIZE),
                overlap=options.get("overlap", settings.CHUNK_OVERLAP),
            )
            logger.info(f"[{job_id}] Created {len(chunks)} chunks")

            # 4. 向量化
            chunk_texts = [chunk["content"] for chunk in chunks]
            embeddings = await self.embedding_service.embed_batch(chunk_texts)
            logger.info(f"[{job_id}] Generated {len(embeddings)} embeddings")

            # 5. 存储到Milvus
            vectors_inserted = await self.vector_service.insert_vectors(
                document_id=document_id,
                chunks=chunks,
                embeddings=embeddings,
            )
            logger.info(f"[{job_id}] Inserted {vectors_inserted} vectors to Milvus")

            # 6. 构建知识图谱（可选）
            graph_nodes_created = 0
            if options.get("build_graph", False):
                graph_nodes_created = await self._build_knowledge_graph(document_id, chunks)
                logger.info(f"[{job_id}] Created {graph_nodes_created} graph nodes")

            # 更新任务状态
            processing_time = time.time() - start_time
            self.jobs[job_id].update(
                {
                    "status": DocumentStatus.INDEXED,
                    "chunks_count": len(chunks),
                    "vectors_count": vectors_inserted,
                    "graph_nodes_count": graph_nodes_created,
                    "processing_time": processing_time,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )

            logger.info(f"[{job_id}] Document processing completed in {processing_time:.2f}s")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{job_id}] Document processing failed: {error_msg}", exc_info=True)

            self.jobs[job_id].update(
                {
                    "status": DocumentStatus.FAILED,
                    "error_message": error_msg,
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """获取任务状态"""
        return self.jobs.get(job_id)

    async def delete_document(self, document_id: str):
        """
        删除文档及其所有索引

        包括:
        - 对象存储中的文件
        - 文本块
        - 向量索引
        - 知识图谱节点
        """
        try:
            # 删除向量
            await self.vector_service.delete_vectors(document_id)

            # 删除文本块
            await self.chunk_service.delete_chunks(document_id)

            # 删除对象存储文件
            await self.storage_service.delete(document_id)

            # 删除知识图谱节点
            await self._delete_graph_nodes(document_id)

            logger.info(f"Document and all indices deleted: {document_id}")

        except Exception as e:
            logger.error(f"Failed to delete document: {e}", exc_info=True)
            raise

    async def _build_knowledge_graph(self, document_id: str, chunks: list[dict[str, Any]]) -> int:
        """构建知识图谱（示例实现）"""
        # 实际应该调用图服务
        logger.info(f"Building knowledge graph for document: {document_id}")
        return len(chunks)  # Mock

    async def _delete_graph_nodes(self, document_id: str):
        """删除知识图谱节点（示例实现）"""
        logger.info(f"Deleting graph nodes for document: {document_id}")
