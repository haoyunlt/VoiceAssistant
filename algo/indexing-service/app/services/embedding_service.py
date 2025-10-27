"""向量化服务"""
import logging
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务（真实实现）"""

    def __init__(self):
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE
        self._embedder: Optional[object] = None
        self._init_embedder()

    def _init_embedder(self):
        """初始化Embedding模型"""
        try:
            # 优先使用BGE-M3模型
            if "bge" in self.model.lower():
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.model)
                logger.info(f"Initialized BGE embedder: {self.model}")
            elif settings.OPENAI_API_KEY:
                # 使用OpenAI API
                logger.info(f"Using OpenAI API for embeddings: {self.model}")
                self._embedder = None  # Will use API calls
            else:
                raise ValueError(
                    "No valid embedding configuration found. "
                    "Set EMBEDDING_MODEL to a BGE model or configure OPENAI_API_KEY"
                )
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}")
            raise

    async def embed(self, text: str) -> List[float]:
        """
        单个文本向量化

        Args:
            text: 文本内容

        Returns:
            向量（List[float]）
        """
        embeddings = await self.embed_batch([text])
        return embeddings[0] if embeddings else []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量文本向量化

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        try:
            logger.info(f"Embedding {len(texts)} texts with model {self.model}")

            if not texts:
                return []

            # 使用BGE模型
            if self._embedder is not None:
                embeddings = self._embedder.encode(
                    texts,
                    batch_size=self.batch_size,
                    show_progress_bar=len(texts) > 100,
                    convert_to_numpy=True,
                )
                result = embeddings.tolist()
                logger.info(f"Generated {len(result)} embeddings using BGE")
                return result

            # 使用OpenAI API
            if settings.OPENAI_API_KEY:
                return await self.embed_with_openai(texts)

            raise ValueError("No valid embedder initialized")

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
