"""向量化服务"""
import logging
from typing import List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务"""

    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    async def embed(self, text: str) -> List[float]:
        """
        单个文本向量化

        Args:
            text: 文本内容

        Returns:
            向量（List[float]）
        """
        return await self.embed_batch([text])[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量文本向量化

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        try:
            # 实际应该调用真实的Embedding API（OpenAI, BGE, etc.）
            # 这里使用Mock实现
            logger.info(f"Embedding {len(texts)} texts with model {self.model}")

            # Mock实现：返回随机向量
            import random
            embeddings = [
                [random.random() for _ in range(self.dimension)]
                for _ in range(len(texts))
            ]

            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Embedding failed: {e}", exc_info=True)
            raise

    async def embed_with_openai(self, texts: List[str]) -> List[List[float]]:
        """
        使用OpenAI API进行向量化

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OPENAI_API_BASE}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "input": texts,
                        "model": "text-embedding-3-small",
                    },
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                # 提取嵌入向量
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings

        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise
