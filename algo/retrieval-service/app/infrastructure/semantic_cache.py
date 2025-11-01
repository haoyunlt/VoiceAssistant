"""
Semantic Cache - 语义缓存实现

功能:
- Query Embedding相似度匹配 (threshold=0.95)
- LRU + TTL淘汰策略
- Bloom Filter防穿透
- Redis存储
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass

import numpy as np
from redis.asyncio import Redis

from app.observability.logging import logger


@dataclass
class CachedResult:
    """缓存结果"""

    query: str
    query_embedding: list[float]
    documents: list[dict]
    score: float
    timestamp: float
    ttl: int  # seconds


class SemanticCache:
    """语义缓存"""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: str = "",
        redis_db: int = 3,
        similarity_threshold: float = 0.95,
        ttl: int = 3600,  # 1小时
        max_cache_size: int = 10000,
    ):
        """
        初始化语义缓存

        Args:
            redis_host: Redis主机
            redis_port: Redis端口
            redis_password: Redis密码
            redis_db: Redis数据库
            similarity_threshold: 相似度阈值
            ttl: 缓存TTL（秒）
            max_cache_size: 最大缓存条目数
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.redis_db = redis_db
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self.max_cache_size = max_cache_size

        self.redis: Redis | None = None
        self._bloom_filter = set()  # 简化的Bloom Filter

        logger.info(
            f"Semantic cache initialized: threshold={similarity_threshold}, "
            f"ttl={ttl}s, max_size={max_cache_size}"
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
            logger.info("Semantic cache connected to Redis")

    async def get(self, query: str, query_embedding: np.ndarray) -> CachedResult | None:
        """
        获取缓存结果

        Args:
            query: 查询文本
            query_embedding: 查询embedding

        Returns:
            缓存结果（如果命中）
        """
        if self.redis is None:
            await self.connect()

        try:
            # 1. Bloom Filter快速检查
            query_hash = self._hash_query(query)
            if query_hash not in self._bloom_filter:
                logger.debug(f"Cache miss (Bloom Filter): {query[:50]}")
                return None

            # 2. 相似度匹配
            cached_result = await self._find_similar_cached(query_embedding)

            if cached_result:
                logger.info(f"Cache hit (similarity={cached_result.score:.3f}): {query[:50]}")
                return cached_result

            logger.debug(f"Cache miss (no similar query): {query[:50]}")
            return None

        except Exception as e:
            logger.error(f"Semantic cache get error: {e}", exc_info=True)
            return None

    async def set(
        self,
        query: str,
        query_embedding: np.ndarray,
        documents: list[dict],
    ):
        """
        设置缓存

        Args:
            query: 查询文本
            query_embedding: 查询embedding
            documents: 文档列表
        """
        if self.redis is None:
            await self.connect()

        try:
            # 1. 添加到Bloom Filter
            query_hash = self._hash_query(query)
            self._bloom_filter.add(query_hash)

            # 2. 存储缓存
            cache_key = f"semantic_cache:{query_hash}"
            cache_data = {
                "query": query,
                "query_embedding": query_embedding.tolist(),
                "documents": documents,
                "timestamp": time.time(),
                "ttl": self.ttl,
            }

            await self.redis.setex(cache_key, self.ttl, json.dumps(cache_data).encode("utf-8"))

            # 3. 添加到LRU列表
            await self.redis.zadd("semantic_cache:lru", {cache_key: time.time()}, nx=True)

            # 4. 检查缓存大小，驱逐最旧的
            await self._evict_if_needed()

            logger.debug(f"Cache set: {query[:50]}")

        except Exception as e:
            logger.error(f"Semantic cache set error: {e}", exc_info=True)

    async def _find_similar_cached(self, query_embedding: np.ndarray) -> CachedResult | None:
        """
        查找相似的缓存查询

        Args:
            query_embedding: 查询embedding

        Returns:
            相似的缓存结果
        """
        # 获取所有缓存键
        cache_keys = await self.redis.keys("semantic_cache:*")

        best_match = None
        best_similarity = 0.0

        for key in cache_keys[:100]:  # 限制检查数量
            if key == b"semantic_cache:lru":
                continue

            try:
                # 读取缓存数据
                cached_data_bytes = await self.redis.get(key)
                if not cached_data_bytes:
                    continue

                cached_data = json.loads(cached_data_bytes.decode("utf-8"))

                # 计算相似度
                cached_embedding = np.array(cached_data["query_embedding"])
                similarity = self._cosine_similarity(query_embedding, cached_embedding)

                # 检查是否超过阈值
                if similarity >= self.similarity_threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = CachedResult(
                        query=cached_data["query"],
                        query_embedding=cached_data["query_embedding"],
                        documents=cached_data["documents"],
                        score=similarity,
                        timestamp=cached_data["timestamp"],
                        ttl=cached_data["ttl"],
                    )

            except Exception as e:
                logger.warning(f"Error checking cached key {key}: {e}")
                continue

        return best_match

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _hash_query(self, query: str) -> str:
        """计算查询hash"""
        return hashlib.md5(query.encode("utf-8")).hexdigest()

    async def _evict_if_needed(self):
        """LRU驱逐"""
        # 获取缓存大小
        cache_size = await self.redis.zcard("semantic_cache:lru")

        if cache_size > self.max_cache_size:
            # 删除最旧的条目
            to_evict = cache_size - self.max_cache_size
            old_keys = await self.redis.zrange("semantic_cache:lru", 0, to_evict - 1)

            for key in old_keys:
                await self.redis.delete(key)
                await self.redis.zrem("semantic_cache:lru", key)

            logger.info(f"Evicted {len(old_keys)} old cache entries")

    async def get_stats(self) -> dict:
        """获取缓存统计"""
        if self.redis is None:
            return {}

        cache_size = await self.redis.zcard("semantic_cache:lru")

        return {
            "cache_size": cache_size,
            "max_cache_size": self.max_cache_size,
            "similarity_threshold": self.similarity_threshold,
            "ttl": self.ttl,
            "bloom_filter_size": len(self._bloom_filter),
        }

    async def clear(self):
        """清空缓存"""
        if self.redis:
            keys = await self.redis.keys("semantic_cache:*")
            if keys:
                await self.redis.delete(*keys)
            self._bloom_filter.clear()
            logger.info("Semantic cache cleared")


# 全局单例
_semantic_cache = None


def get_semantic_cache() -> SemanticCache:
    """获取全局语义缓存"""
    global _semantic_cache
    if _semantic_cache is None:
        from app.core.config import settings

        _semantic_cache = SemanticCache(
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_password=settings.REDIS_PASSWORD,
            redis_db=settings.REDIS_DB,
            ttl=settings.CACHE_TTL,
        )
    return _semantic_cache


# 使用示例
if __name__ == "__main__":

    async def test():
        cache = SemanticCache()
        await cache.connect()

        # 模拟query embedding
        query1 = "Python programming tutorial"
        emb1 = np.random.randn(384).astype(np.float32)

        # 设置缓存
        await cache.set(query1, emb1, [{"id": "doc1", "content": "Test doc"}])

        # 获取缓存 (相同query)
        result = await cache.get(query1, emb1)
        print(f"Cache hit: {result is not None}")

        # 获取缓存 (相似query)
        query2 = "Python programming guide"
        emb2 = emb1 + np.random.randn(384) * 0.01  # 非常相似
        result2 = await cache.get(query2, emb2)
        print(f"Similar query hit: {result2 is not None}")

        # 统计
        stats = await cache.get_stats()
        print(f"Cache stats: {stats}")

    asyncio.run(test())
