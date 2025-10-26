"""BGE-M3 Embedder - 向量化模块（与 Indexing Service 共享）"""

import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class BGE_M3_Embedder:
    """BGE-M3 Embedding 模型"""

    def __init__(self, model_name: str = "BAAI/bge-m3", batch_size: int = 32):
        """
        初始化 Embedder

        Args:
            model_name: 模型名称
            batch_size: 批处理大小
        """
        self.model_name = model_name
        self.batch_size = batch_size

        logger.info(f"Loading model: {model_name}...")

        # 加载模型
        self.model = SentenceTransformer(model_name)

        # 获取向量维度
        self.dimension = self.model.get_sentence_embedding_dimension()

        logger.info(f"Model loaded successfully. Dimension: {self.dimension}")

    async def embed(self, text: str) -> List[float]:
        """
        单个文本向量化

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.dimension

        # 生成向量
        embedding = self.model.encode(text, convert_to_numpy=True)

        return embedding.tolist()

    async def embed_query(self, query: str) -> List[float]:
        """
        查询向量化（添加查询特定的处理）

        Args:
            query: 查询文本

        Returns:
            向量列表
        """
        # 对于 BGE 模型，查询需要添加特殊前缀
        query_with_prefix = f"为这个句子生成表示以用于检索相关文章：{query}"

        return await self.embed(query_with_prefix)

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.dimension
