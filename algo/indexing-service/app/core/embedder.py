"""
BGE-M3 Embedder - 向量化模块
"""

import logging

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

    async def embed(self, text: str) -> list[float]:
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

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量文本向量化

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            logger.warning("Empty texts list provided for embedding")
            return []

        # 过滤空文本
        valid_texts = [text if text and text.strip() else " " for text in texts]

        # 批量生成向量
        embeddings = self.model.encode(
            valid_texts,
            batch_size=self.batch_size,
            show_progress_bar=len(valid_texts) > 100,
            convert_to_numpy=True,
        )

        logger.info(f"Generated {len(embeddings)} embeddings")

        return embeddings.tolist()

    async def embed_query(self, query: str) -> list[float]:
        """
        查询向量化（可以添加查询特定的处理）

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


class CachedEmbedder(BGE_M3_Embedder):
    """带缓存的 Embedder"""

    def __init__(
        self, model_name: str = "BAAI/bge-m3", batch_size: int = 32, cache_size: int = 10000
    ):
        super().__init__(model_name, batch_size)

        # 简单的 LRU 缓存
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(f"Cached embedder initialized with cache size: {cache_size}")

    async def embed(self, text: str) -> list[float]:
        """
        带缓存的单个文本向量化
        """
        # 计算文本哈希
        text_hash = hash(text)

        # 检查缓存
        if text_hash in self.cache:
            self.cache_hits += 1
            return self.cache[text_hash]

        # 缓存未命中，生成向量
        self.cache_misses += 1
        embedding = await super().embed(text)

        # 添加到缓存
        if len(self.cache) >= self.cache_size:
            # 简单策略：删除第一个元素
            self.cache.pop(next(iter(self.cache)))

        self.cache[text_hash] = embedding

        return embedding

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0

        return {
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
        }
