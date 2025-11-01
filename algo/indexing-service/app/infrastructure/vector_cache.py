"""
两级向量缓存系统
L1: 内存 LRU 缓存 (快速但容量有限)
L2: Redis 缓存 (容量大但稍慢)
"""

import hashlib
import logging
import pickle
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Prometheus 指标
CACHE_HITS = Counter(
    "vector_cache_hits_total",
    "Total number of cache hits",
    ["level", "model"],  # level: L1/L2
)
CACHE_MISSES = Counter(
    "vector_cache_misses_total",
    "Total number of cache misses",
    ["model"],
)
CACHE_SIZE = Gauge(
    "vector_cache_size",
    "Current size of the cache",
    ["level", "model"],
)
CACHE_LATENCY = Histogram(
    "vector_cache_latency_seconds",
    "Cache operation latency",
    ["operation", "level"],  # operation: get/set, level: L1/L2
    buckets=[0.0001, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
)


class LRUCache:
    """内存 LRU 缓存"""

    def __init__(self, max_size: int = 10000):
        """
        初始化 LRU 缓存

        Args:
            max_size: 最大缓存条目数
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key -> (value, timestamp)
        self.hits = 0
        self.misses = 0

        logger.info(f"LRUCache initialized with max_size={max_size}")

    def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在返回 None
        """
        if key in self.cache:
            # 移到最后（标记为最近使用）
            self.cache.move_to_end(key)
            value, _ = self.cache[key]
            self.hits += 1
            return value

        self.misses += 1
        return None

    def set(self, key: str, value: Any):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
        """
        # 如果已存在，更新并移到最后
        if key in self.cache:
            self.cache.move_to_end(key)

        # 添加新条目
        self.cache[key] = (value, time.time())

        # 如果超过最大大小，删除最旧的条目
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)

    def delete(self, key: str):
        """
        删除缓存条目

        Args:
            key: 缓存键
        """
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)

    def hit_rate(self) -> float:
        """计算缓存命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "size": self.size(),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate(),
        }


class VectorCache:
    """两级向量缓存"""

    def __init__(
        self,
        redis_client,
        l1_max_size: int = 10000,
        l2_ttl: int = 604800,  # 7天
        key_prefix: str = "vector_cache",
    ):
        """
        初始化两级缓存

        Args:
            redis_client: Redis 客户端
            l1_max_size: L1 缓存最大条目数
            l2_ttl: L2 缓存 TTL（秒）
            key_prefix: Redis 键前缀
        """
        self.redis = redis_client
        self.l1_cache = LRUCache(max_size=l1_max_size)
        self.l2_ttl = l2_ttl
        self.key_prefix = key_prefix

        # 统计信息
        self.l2_hits = 0
        self.l2_misses = 0
        self.total_computes = 0

        logger.info(f"VectorCache initialized: L1_size={l1_max_size}, L2_TTL={l2_ttl}s")

    async def get_or_compute(
        self,
        text: str,
        model: str,
        compute_fn: Callable,
    ) -> list[float]:
        """
        获取或计算向量

        策略:
        1. 先查 L1 缓存（内存）
        2. 未命中则查 L2 缓存（Redis）
        3. 都未命中则调用 compute_fn 计算
        4. 计算结果写入 L1 和 L2

        Args:
            text: 文本内容
            model: 模型名称
            compute_fn: 计算函数（返回向量）

        Returns:
            向量列表
        """
        # 生成缓存键
        cache_key = self._generate_cache_key(text, model)

        # 1. 查询 L1 缓存
        start_time = time.time()
        vector = self.l1_cache.get(cache_key)
        CACHE_LATENCY.labels(operation="get", level="L1").observe(time.time() - start_time)

        if vector is not None:
            CACHE_HITS.labels(level="L1", model=model).inc()
            logger.debug(f"L1 cache hit: {cache_key[:16]}...")
            return vector

        # 2. 查询 L2 缓存
        start_time = time.time()
        vector = await self._get_from_redis(cache_key)
        CACHE_LATENCY.labels(operation="get", level="L2").observe(time.time() - start_time)

        if vector is not None:
            CACHE_HITS.labels(level="L2", model=model).inc()
            self.l2_hits += 1

            # 写回 L1 缓存
            start_time = time.time()
            self.l1_cache.set(cache_key, vector)
            CACHE_LATENCY.labels(operation="set", level="L1").observe(time.time() - start_time)

            logger.debug(f"L2 cache hit: {cache_key[:16]}...")
            return vector

        # 3. 缓存未命中，计算向量
        CACHE_MISSES.labels(model=model).inc()
        self.l2_misses += 1
        self.total_computes += 1

        logger.debug(f"Cache miss, computing: {cache_key[:16]}...")

        vector = await compute_fn()

        # 4. 写入两级缓存
        await self._set_cache(cache_key, vector, model)

        return vector

    async def get_batch_or_compute(
        self,
        texts: list[str],
        model: str,
        compute_fn: Callable[[list[str]], list[list[float]]],
    ) -> list[list[float]]:
        """
        批量获取或计算向量

        策略:
        1. 先批量查询缓存，记录未命中的文本
        2. 对未命中的文本批量计算向量
        3. 将计算结果写入缓存
        4. 返回完整结果

        Args:
            texts: 文本列表
            model: 模型名称
            compute_fn: 批量计算函数

        Returns:
            向量列表
        """
        results = [None] * len(texts)
        cache_keys = [self._generate_cache_key(text, model) for text in texts]

        # 1. 批量查询缓存
        uncached_indices = []
        uncached_texts = []

        for i, (text, cache_key) in enumerate(zip(texts, cache_keys, strict=False)):
            # 先查 L1
            vector = self.l1_cache.get(cache_key)

            if vector is not None:
                CACHE_HITS.labels(level="L1", model=model).inc()
                results[i] = vector
                continue

            # 再查 L2
            vector = await self._get_from_redis(cache_key)

            if vector is not None:
                CACHE_HITS.labels(level="L2", model=model).inc()
                self.l2_hits += 1

                # 写回 L1
                self.l1_cache.set(cache_key, vector)
                results[i] = vector
                continue

            # 未命中
            CACHE_MISSES.labels(model=model).inc()
            self.l2_misses += 1
            uncached_indices.append(i)
            uncached_texts.append(text)

        # 2. 批量计算未命中的向量
        if uncached_texts:
            logger.debug(f"Cache miss for {len(uncached_texts)}/{len(texts)} texts, computing...")

            computed_vectors = await compute_fn(uncached_texts)
            self.total_computes += len(uncached_texts)

            # 3. 写入缓存并更新结果
            for idx, vector in zip(uncached_indices, computed_vectors, strict=False):
                cache_key = cache_keys[idx]
                await self._set_cache(cache_key, vector, model)
                results[idx] = vector

        return results

    async def _set_cache(self, cache_key: str, vector: list[float], model: str):
        """
        写入两级缓存

        Args:
            cache_key: 缓存键
            vector: 向量
            model: 模型名称
        """
        # 写入 L1
        start_time = time.time()
        self.l1_cache.set(cache_key, vector)
        CACHE_LATENCY.labels(operation="set", level="L1").observe(time.time() - start_time)

        # 写入 L2
        start_time = time.time()
        await self._set_to_redis(cache_key, vector)
        CACHE_LATENCY.labels(operation="set", level="L2").observe(time.time() - start_time)

        # 更新缓存大小指标
        CACHE_SIZE.labels(level="L1", model=model).set(self.l1_cache.size())

    def _generate_cache_key(self, text: str, model: str) -> str:
        """
        生成缓存键

        使用 MD5 哈希文本内容 + 模型名称

        Args:
            text: 文本内容
            model: 模型名称

        Returns:
            缓存键
        """
        content = f"{model}:{text}"
        text_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{self.key_prefix}:{model}:{text_hash}"

    async def _get_from_redis(self, cache_key: str) -> list[float] | None:
        """
        从 Redis 获取向量

        Args:
            cache_key: 缓存键

        Returns:
            向量列表，如果不存在返回 None
        """
        try:
            data = await self.redis.get(cache_key)

            if data:
                # 反序列化
                vector = pickle.loads(data)
                return vector

            return None

        except Exception as e:
            logger.error(f"Failed to get from Redis: {e}")
            return None

    async def _set_to_redis(self, cache_key: str, vector: list[float]):
        """
        写入 Redis

        Args:
            cache_key: 缓存键
            vector: 向量列表
        """
        try:
            # 序列化
            data = pickle.dumps(vector)

            # 写入 Redis（带 TTL）
            await self.redis.setex(cache_key, self.l2_ttl, data)

        except Exception as e:
            logger.error(f"Failed to set to Redis: {e}")

    async def invalidate(self, text: str, model: str):
        """
        使缓存失效

        Args:
            text: 文本内容
            model: 模型名称
        """
        cache_key = self._generate_cache_key(text, model)

        # 从 L1 删除
        self.l1_cache.delete(cache_key)

        # 从 L2 删除
        try:
            await self.redis.delete(cache_key)
        except Exception as e:
            logger.error(f"Failed to delete from Redis: {e}")

    async def clear(self, model: str | None = None):
        """
        清空缓存

        Args:
            model: 模型名称，如果为 None 则清空所有
        """
        # 清空 L1
        self.l1_cache.clear()

        # 清空 L2
        pattern = f"{self.key_prefix}:{model}:*" if model else f"{self.key_prefix}:*"

        try:
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

                if keys:
                    await self.redis.delete(*keys)

                if cursor == 0:
                    break

            logger.info(f"Cleared cache for pattern: {pattern}")

        except Exception as e:
            logger.error(f"Failed to clear Redis cache: {e}")

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        l1_stats = self.l1_cache.stats()

        total_requests = l1_stats["hits"] + l1_stats["misses"]
        l2_requests = l1_stats["misses"]  # L2 请求数 = L1 未命中数

        # 计算整体命中率
        total_hits = l1_stats["hits"] + self.l2_hits
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

        # 计算 L2 命中率
        l2_hit_rate = self.l2_hits / l2_requests if l2_requests > 0 else 0.0

        return {
            "L1": l1_stats,
            "L2": {
                "hits": self.l2_hits,
                "misses": self.l2_misses,
                "hit_rate": l2_hit_rate,
            },
            "overall": {
                "total_requests": total_requests,
                "total_hits": total_hits,
                "total_misses": self.l2_misses,
                "hit_rate": overall_hit_rate,
                "compute_count": self.total_computes,
                "cache_efficiency": 1 - (self.total_computes / total_requests)
                if total_requests > 0
                else 0.0,
            },
        }

    async def warmup(
        self,
        texts: list[str],
        model: str,
        compute_fn: Callable[[list[str]], list[list[float]]],
        batch_size: int = 32,
    ):
        """
        缓存预热

        批量计算向量并写入缓存

        Args:
            texts: 文本列表
            model: 模型名称
            compute_fn: 批量计算函数
            batch_size: 批量大小
        """
        logger.info(f"Starting cache warmup for {len(texts)} texts...")

        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_num = i // batch_size + 1

            logger.info(f"Warmup batch {batch_num}/{total_batches}")

            # 计算向量
            vectors = await compute_fn(batch_texts)

            # 写入缓存
            for text, vector in zip(batch_texts, vectors, strict=False):
                cache_key = self._generate_cache_key(text, model)
                await self._set_cache(cache_key, vector, model)

        logger.info(f"Cache warmup completed: {len(texts)} texts cached")


class MultiModelVectorCache:
    """多模型向量缓存（支持多个模型共享缓存）"""

    def __init__(
        self,
        redis_client,
        l1_max_size_per_model: int = 10000,
        l2_ttl: int = 604800,
    ):
        """
        初始化多模型缓存

        Args:
            redis_client: Redis 客户端
            l1_max_size_per_model: 每个模型的 L1 缓存大小
            l2_ttl: L2 缓存 TTL
        """
        self.redis = redis_client
        self.l1_max_size_per_model = l1_max_size_per_model
        self.l2_ttl = l2_ttl

        # 每个模型一个独立的缓存实例
        self.caches: dict[str, VectorCache] = {}

        logger.info(
            f"MultiModelVectorCache initialized: "
            f"L1_per_model={l1_max_size_per_model}, L2_TTL={l2_ttl}s"
        )

    def _get_or_create_cache(self, model: str) -> VectorCache:
        """
        获取或创建模型的缓存实例

        Args:
            model: 模型名称

        Returns:
            VectorCache 实例
        """
        if model not in self.caches:
            self.caches[model] = VectorCache(
                redis_client=self.redis,
                l1_max_size=self.l1_max_size_per_model,
                l2_ttl=self.l2_ttl,
                key_prefix=f"vector_cache:{model}",
            )
            logger.info(f"Created cache for model: {model}")

        return self.caches[model]

    async def get_or_compute(
        self,
        text: str,
        model: str,
        compute_fn: Callable,
    ) -> list[float]:
        """
        获取或计算向量

        Args:
            text: 文本内容
            model: 模型名称
            compute_fn: 计算函数

        Returns:
            向量列表
        """
        cache = self._get_or_create_cache(model)
        return await cache.get_or_compute(text, model, compute_fn)

    async def get_batch_or_compute(
        self,
        texts: list[str],
        model: str,
        compute_fn: Callable[[list[str]], list[list[float]]],
    ) -> list[list[float]]:
        """
        批量获取或计算向量

        Args:
            texts: 文本列表
            model: 模型名称
            compute_fn: 批量计算函数

        Returns:
            向量列表
        """
        cache = self._get_or_create_cache(model)
        return await cache.get_batch_or_compute(texts, model, compute_fn)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """
        获取所有模型的缓存统计

        Returns:
            模型名称 -> 统计信息的字典
        """
        return {model: cache.get_stats() for model, cache in self.caches.items()}

    async def clear_all(self):
        """清空所有缓存"""
        for model, cache in self.caches.items():
            await cache.clear(model)
            logger.info(f"Cleared cache for model: {model}")
