"""Embedding服务"""

import torch
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """Embedding服务"""

    def __init__(self):
        """初始化"""
        # 加载BGE-M3模型（中文优化）
        model_name = settings.get("EMBEDDING_MODEL", "BAAI/bge-m3")

        try:
            self.model = SentenceTransformer(model_name)

            # 使用GPU（如果可用）
            if torch.cuda.is_available():
                self.model = self.model.to("cuda")

            logger.info(f"Embedding model {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

        # 查询指令前缀
        self.query_instruction = "Represent this sentence for searching relevant passages: "

        # 文档指令前缀
        self.doc_instruction = ""

    async def embed_query(self, query: str) -> list[float]:
        """查询向量化

        Args:
            query: 查询文本

        Returns:
            查询向量
        """
        try:
            # 添加查询指令
            query_with_instruction = self.query_instruction + query

            # 编码
            embedding = self.model.encode(
                query_with_instruction, normalize_embeddings=True, convert_to_numpy=True
            )

            return embedding.tolist()
        except Exception as e:
            logger.error(f"Query embedding error: {e}")
            raise

    async def embed_documents(
        self, texts: list[str], batch_size: int = 32, show_progress: bool = False
    ) -> list[list[float]]:
        """批量文档向量化

        Args:
            texts: 文本列表
            batch_size: 批次大小
            show_progress: 是否显示进度

        Returns:
            向量列表
        """
        try:
            # 添加文档指令（如果有）
            if self.doc_instruction:
                texts_with_instruction = [self.doc_instruction + text for text in texts]
            else:
                texts_with_instruction = texts

            # 批量编码
            embeddings = self.model.encode(
                texts_with_instruction,
                normalize_embeddings=True,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Document embedding error: {e}")
            raise

    async def embed_single(self, text: str, is_query: bool = False) -> list[float]:
        """单个文本向量化

        Args:
            text: 文本
            is_query: 是否是查询

        Returns:
            向量
        """
        try:
            # 添加指令
            if is_query:
                text_with_instruction = self.query_instruction + text
            elif self.doc_instruction:
                text_with_instruction = self.doc_instruction + text
            else:
                text_with_instruction = text

            # 编码
            embedding = self.model.encode(
                text_with_instruction, normalize_embeddings=True, convert_to_numpy=True
            )

            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """获取向量维度

        Returns:
            向量维度
        """
        return self.model.get_sentence_embedding_dimension()

    async def compute_similarity(
        self, query_embedding: list[float], doc_embeddings: list[list[float]]
    ) -> list[float]:
        """计算相似度

        Args:
            query_embedding: 查询向量
            doc_embeddings: 文档向量列表

        Returns:
            相似度分数列表
        """
        try:
            import numpy as np

            query_vec = np.array(query_embedding)
            doc_vecs = np.array(doc_embeddings)

            # 余弦相似度（向量已归一化，直接点积）
            similarities = np.dot(doc_vecs, query_vec)

            return similarities.tolist()
        except Exception as e:
            logger.error(f"Similarity computation error: {e}")
            raise
