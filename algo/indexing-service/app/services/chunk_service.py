"""文本分块服务"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChunkService:
    """文本分块服务"""

    def __init__(self):
        self.chunks_store: Dict[str, List[Dict[str, Any]]] = {}  # document_id -> chunks

    async def create_chunks(
        self,
        document_id: str,
        content: str,
        chunk_size: int = 512,
        overlap: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        将文本分块

        Args:
            document_id: 文档ID
            content: 文本内容
            chunk_size: 块大小（字符数）
            overlap: 重叠大小

        Returns:
            文本块列表
        """
        try:
            chunks = []
            position = 0
            chunk_index = 0

            while position < len(content):
                # 提取块
                end_position = min(position + chunk_size, len(content))
                chunk_content = content[position:end_position]

                # 创建块记录
                chunk = {
                    "id": f"chunk_{uuid.uuid4().hex[:16]}",
                    "document_id": document_id,
                    "content": chunk_content,
                    "position": chunk_index,
                    "chunk_size": len(chunk_content),
                    "start_pos": position,
                    "end_pos": end_position,
                    "created_at": datetime.utcnow().isoformat(),
                }

                chunks.append(chunk)

                # 移动到下一个块（考虑重叠）
                position += chunk_size - overlap
                chunk_index += 1

            # 存储块
            self.chunks_store[document_id] = chunks

            logger.info(f"Created {len(chunks)} chunks for document {document_id}")
            return chunks

        except Exception as e:
            logger.error(f"Failed to create chunks: {e}", exc_info=True)
            raise

    async def get_chunks_by_document(
        self,
        document_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取文档的所有块"""
        chunks = self.chunks_store.get(document_id, [])
        return chunks[offset : offset + limit]

    async def get_chunk_by_id(self, chunk_id: str) -> Dict[str, Any]:
        """获取单个块"""
        for chunks in self.chunks_store.values():
            for chunk in chunks:
                if chunk["id"] == chunk_id:
                    return chunk
        return None

    async def delete_chunks(self, document_id: str):
        """删除文档的所有块"""
        if document_id in self.chunks_store:
            del self.chunks_store[document_id]
            logger.info(f"Deleted chunks for document: {document_id}")

    async def reindex_document(self, document_id: str) -> Dict[str, Any]:
        """重新索引文档的块"""
        chunks = self.chunks_store.get(document_id, [])
        return {"chunks_count": len(chunks)}
