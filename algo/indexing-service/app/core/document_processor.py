"""
Document Processor - 文档处理协调器

负责协调整个文档处理流程：
1. 下载文档
2. 解析文档
3. 分块
4. 向量化
5. 存储到 Milvus
6. 构建图谱
"""

import asyncio
import logging
import time
from typing import Dict, List

from app.core.chunker import DocumentChunker
from app.core.embedder import BGE_M3_Embedder
from app.core.graph_builder import GraphBuilder
from app.core.parsers import ParserFactory
from app.infrastructure.minio_client import MinIOClient
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store_client import VectorStoreClient

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器"""

    def __init__(self):
        """初始化处理器"""
        # 初始化组件
        self.parser_factory = ParserFactory()
        self.chunker = DocumentChunker()
        self.embedder = BGE_M3_Embedder()
        self.vector_store_client = VectorStoreClient()
        self.minio_client = MinIOClient()
        self.neo4j_client = Neo4jClient()
        self.graph_builder = GraphBuilder(self.neo4j_client)

        # 统计信息
        self.stats = {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_chunks": 0,
            "total_vectors": 0,
        }

        logger.info("Document processor initialized")

    async def process_document(self, document_id: str, tenant_id: str = None,
                              user_id: str = None, file_path: str = None) -> Dict:
        """处理文档（完整流程）"""
        start_time = time.time()

        try:
            logger.info(f"Processing document: {document_id}")

            # 1. 下载文档
            file_data = await self._download_document(file_path or document_id)

            # 2. 解析文档
            text = await self._parse_document(file_data, file_path)

            # 3. 分块
            chunks = await self._chunk_document(text, document_id)

            # 4. 向量化
            embeddings = await self._vectorize_chunks(chunks)

            # 5. 存储到 Milvus
            await self._store_vectors(chunks, embeddings, document_id, tenant_id)

            # 6. 构建图谱 (异步)
            asyncio.create_task(
                self._build_graph(text, document_id, tenant_id)
            )

            # 更新统计
            self.stats["total_processed"] += 1
            self.stats["total_success"] += 1
            self.stats["total_chunks"] += len(chunks)
            self.stats["total_vectors"] += len(embeddings)

            duration = time.time() - start_time

            logger.info(f"Document {document_id} processed successfully in {duration:.2f}s")

            return {
                "status": "success",
                "document_id": document_id,
                "chunks_count": len(chunks),
                "duration": duration,
            }

        except Exception as e:
            self.stats["total_processed"] += 1
            self.stats["total_failed"] += 1

            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)

            return {
                "status": "failed",
                "document_id": document_id,
                "error": str(e),
            }

    async def _download_document(self, file_path: str) -> bytes:
        """下载文档"""
        logger.info(f"Downloading document: {file_path}")
        return await self.minio_client.download_file(file_path)

    async def _parse_document(self, file_data: bytes, file_path: str) -> str:
        """解析文档"""
        logger.info(f"Parsing document: {file_path}")

        # 根据文件扩展名选择解析器
        parser = self.parser_factory.get_parser(file_path)

        # 解析文档
        text = await parser.parse(file_data)

        logger.info(f"Parsed document, text length: {len(text)} chars")

        return text

    async def _chunk_document(self, text: str, document_id: str) -> List[Dict]:
        """分块文档"""
        logger.info(f"Chunking document: {document_id}")

        chunks = await self.chunker.chunk(text, document_id)

        logger.info(f"Created {len(chunks)} chunks")

        return chunks

    async def _vectorize_chunks(self, chunks: List[Dict]) -> List[List[float]]:
        """向量化分块"""
        logger.info(f"Vectorizing {len(chunks)} chunks")

        # 提取文本
        texts = [chunk["content"] for chunk in chunks]

        # 批量向量化
        embeddings = await self.embedder.embed_batch(texts)

        logger.info(f"Generated {len(embeddings)} embeddings")

        return embeddings

    async def _store_vectors(self, chunks: List[Dict], embeddings: List[List[float]],
                           document_id: str, tenant_id: str = None):
        """存储向量到 Milvus"""
        logger.info(f"Storing {len(embeddings)} vectors to Milvus")

        # 准备数据
        data = []
        for chunk, embedding in zip(chunks, embeddings):
            data.append({
                "chunk_id": chunk["id"],
                "document_id": document_id,
                "tenant_id": tenant_id or "default",
                "content": chunk["content"],
                "embedding": embedding,
                "metadata": chunk.get("metadata", {}),
            })

        # 批量插入
        await self.vector_store_client.insert_batch(data)

        logger.info(f"Stored {len(data)} vectors successfully")

    async def _build_graph(self, text: str, document_id: str, tenant_id: str = None):
        """构建知识图谱"""
        try:
            logger.info(f"Building knowledge graph for document: {document_id}")

            # 提取实体和关系
            entities, relationships = await self.graph_builder.extract(text)

            # 存储到 Neo4j
            await self.graph_builder.build(
                entities=entities,
                relationships=relationships,
                document_id=document_id,
                tenant_id=tenant_id,
            )

            logger.info(f"Knowledge graph built: {len(entities)} entities, {len(relationships)} relationships")

        except Exception as e:
            logger.error(f"Error building graph: {e}", exc_info=True)

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "vector_store_count": await self.vector_store_client.count(),
            "neo4j_nodes": await self.neo4j_client.count_nodes(),
            "neo4j_relationships": await self.neo4j_client.count_relationships(),
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up document processor...")

        # 关闭连接
        await self.vector_store_client.close()
        await self.neo4j_client.close()
        await self.minio_client.close()

        logger.info("Document processor cleanup complete")


# ========================================
# 文档处理结果
# ========================================

class ProcessingResult:
    """处理结果"""

    def __init__(self, document_id: str, status: str,
                 chunks_count: int = 0, duration: float = 0,
                 error: str = None):
        self.document_id = document_id
        self.status = status
        self.chunks_count = chunks_count
        self.duration = duration
        self.error = error

    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            "document_id": self.document_id,
            "status": self.status,
            "chunks_count": self.chunks_count,
            "duration": self.duration,
        }

        if self.error:
            result["error"] = self.error

        return result

    def is_success(self) -> bool:
        """是否成功"""
        return self.status == "success"
