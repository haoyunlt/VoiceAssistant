"""
Embedding Cache - Embedding缓存

功能:
- Query Embedding缓存
- Document Embedding预计算
- Redis存储
- LRU + TTL淘汰

目标:
- Embedding请求减少≥40%
- 缓存命中延迟≤5ms
"""

import asyncio
import hashlib
import json
import time
from typing import List, Optional

import numpy as np
from redis.asyncio import Redis

from app.observability.logging import logger


class EmbeddingCache:
    """Embedding缓存"""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: str = "",
        redis_db: int = 4,
        ttl: int = 86400,  # 24小时
        max_cache_size: int = 100000,
    ):
        """
        初始化Embedding缓存

        Args:
            redis_host: Redis主机
            redis_port: Redis端口
            redis_password: Redis密码
            redis_db: Redis数据库
            ttl: 缓存TTL（秒）
            max_cache_size: 最大缓存条目数
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.ttl = ttl
        self.max_cache_size = max_cache_size

        self.redis: Optional[Redis] = None

        logger.info(
            f"Embedding cache initialized: ttl={ttl}s, max_size={max_cache_size}"
        )

    async def connect(self):
        """连接Redis"""
        if self.redis is None:
            self.redis = Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password or None,
                db=self.redis_db,
                decode_responses=False,
            )
            logger.info("Embedding cache connected to Redis")

    async def get(self, text: str, model: str = "default") -> Optional[np.ndarray]:
        """
        获取缓存的embedding

        Args:
            text: 文本
            model: 模型名称

        Returns:
            Embedding向量（如果命中）
        """
        if self.redis is None:
            await self.connect()

        try:
            cache_key = self._make_key(text, model)
            cached_bytes = await self.redis.get(cache_key)

            if cached_bytes:
                # 反序列化
                embedding = np.frombuffer(cached_bytes, dtype=np.float32)
                logger.debug(f"Embedding cache hit: {text[:50]}")
                return embedding

            logger.debug(f"Embedding cache miss: {text[:50]}")
            return None

        except Exception as e:
            logger.error(f"Embedding cache get error: {e}", exc_info=True)
            return None

    async def set(
        self, text: str, embedding: np.ndarray, model: str = "default"
    ):
        """
        设置缓存

        Args:
            text: 文本
            embedding: Embedding向量
            model: 模型名称
        """
        if self.redis is None:
            await self.connect()

        try:
            cache_key = self._make_key(text, model)

            # 序列化
            embedding_bytes = embedding.astype(np.float32).tobytes()

            # 存储
            await self.redis.setex(cache_key, self.ttl, embedding_bytes)

            # 添加到LRU
            await self.redis.zadd(
                "embedding_cache:lru", {cache_key: time.time()}, nx=True
            )

            # 检查缓存大小
            await self._evict_if_needed()

            logger.debug(f"Embedding cached: {text[:50]}")

        except Exception as e:
            logger.error(f"Embedding cache set error: {e}", exc_info=True)

    async def get_batch(
        self, texts: List[str], model: str = "default"
    ) -> List[Optional[np.ndarray]]:
        """
        批量获取缓存

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            Embedding列表（None表示未命中）
        """
        tasks = [self.get(text, model) for text in texts]
        return await asyncio.gather(*tasks)

    async def set_batch(
        self, texts: List[str], embeddings: List[np.ndarray], model: str = "default"
    ):
        """
        批量设置缓存

        Args:
            texts: 文本列表
            embeddings: Embedding列表
            model: 模型名称
        """
        tasks = [
            self.set(text, emb, model) for text, emb in zip(texts, embeddings)
        ]
        await asyncio.gather(*tasks)

    def _make_key(self, text: str, model: str) -> str:
        """生成缓存键"""
        # 使用hash避免键过长
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"embedding:{model}:{text_hash}"

    async def _evict_if_needed(self):
        """LRU驱逐"""
        cache_size = await self.redis.zcard("embedding_cache:lru")

        if cache_size > self.max_cache_size:
            # 删除最旧的条目
            to_evict = cache_size - self.max_cache_size
            old_keys = await self.redis.zrange("embedding_cache:lru", 0, to_evict - 1)

            for key in old_keys:
                await self.redis.delete(key)
                await self.redis.zrem("embedding_cache:lru", key)

            logger.info(f"Evicted {len(old_keys)} old embedding cache entries")

    async def get_stats(self) -> dict:
        """获取缓存统计"""
        if self.redis is None:
            return {}

        cache_size = await self.redis.zcard("embedding_cache:lru")

        return {
            "cache_size": cache_size,
            "max_cache_size": self.max_cache_size,
            "ttl": self.ttl,
        }

    async def clear(self):
        """清空缓存"""
        if self.redis:
            keys = await self.redis.keys("embedding:*")
            if keys:
                await self.redis.delete(*keys)
            await self.redis.delete("embedding_cache:lru")
            logger.info("Embedding cache cleared")


# 全局单例
_embedding_cache = None


def get_embedding_cache() -> EmbeddingCache:
    """获取全局Embedding缓存"""
    global _embedding_cache
    if _embedding_cache is None:
        from app.core.config import settings

        _embedding_cache = EmbeddingCache(
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_password=settings.REDIS_PASSWORD,
            redis_db=4,  # 使用不同的DB
            ttl=86400,  # 24小时
        )
    return _embedding_cache


# 使用示例
if __name__ == "__main__":

    async def test():
        cache = EmbeddingCache()
        await cache.connect()

        # 模拟embedding
        text = "Python programming tutorial"
        embedding = np.random.randn(384).astype(np.float32)

        # 设置缓存
        await cache.set(text, embedding)

        # 获取缓存
        cached_emb = await cache.get(text)
        print(f"Cache hit: {cached_emb is not None}")

        if cached_emb is not None:
            print(f"Embeddings match: {np.allclose(embedding, cached_emb)}")

        # 统计
        stats = await cache.get_stats()
        print(f"Cache stats: {stats}")

    asyncio.run(test())
