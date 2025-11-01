"""改进的缓存服务 - 语义缓存 + 指标."""

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional

from prometheus_client import Counter, Gauge, Histogram
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


# Prometheus 指标
cache_hit_total = Counter(
    "model_adapter_cache_hit_total",
    "Total cache hits",
    ["provider", "model"],
)

cache_miss_total = Counter(
    "model_adapter_cache_miss_total",
    "Total cache misses",
    ["provider", "model"],
)

cache_set_total = Counter(
    "model_adapter_cache_set_total",
    "Total cache sets",
    ["provider", "model"],
)

cache_size = Gauge(
    "model_adapter_cache_size",
    "Current cache size (number of entries)",
)

cache_latency = Histogram(
    "model_adapter_cache_latency_seconds",
    "Cache operation latency",
    ["operation"],  # get, set
)


class SemanticCache:
    """语义缓存服务."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "model_adapter:cache",
        default_ttl: int = 120,  # 2分钟 (短时缓存)
        enabled: bool = True,
    ):
        """
        初始化缓存服务.

        Args:
            redis_url: Redis连接URL
            key_prefix: 缓存键前缀
            default_ttl: 默认TTL(秒)
            enabled: 是否启用缓存
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.enabled = enabled
        self._redis: Optional[Redis] = None

        logger.info(
            f"SemanticCache initialized: enabled={enabled}, ttl={default_ttl}s"
        )

    async def connect(self):
        """连接到Redis."""
        if not self.enabled:
            return

        try:
            self._redis = Redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # 测试连接
            await self._redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}, cache disabled")
            self.enabled = False

    async def close(self):
        """关闭Redis连接."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")

    def _generate_cache_key(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        生成缓存键.

        策略: 对最近3轮对话 + 模型参数生成哈希

        Args:
            provider: 提供商
            model: 模型名称
            messages: 消息列表
            temperature: 温度
            **kwargs: 其他参数

        Returns:
            缓存键
        """
        # 只取最近3轮对话 (避免上下文过长导致缓存失效)
        recent_messages = messages[-3:] if len(messages) > 3 else messages

        # 构建缓存键数据
        cache_data = {
            "provider": provider,
            "model": model,
            "messages": recent_messages,
            "temperature": round(temperature, 2),  # 四舍五入避免微小差异
        }

        # 序列化并生成哈希
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        hash_value = hashlib.sha256(cache_str.encode()).hexdigest()[:16]  # 短哈希

        return f"{self.key_prefix}:{provider}:{model}:{hash_value}"

    async def get(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        **kwargs,
    ) -> Optional[dict[str, Any]]:
        """
        从缓存获取响应.

        Args:
            provider: 提供商
            model: 模型名称
            messages: 消息列表
            temperature: 温度
            **kwargs: 其他参数

        Returns:
            缓存的响应 (如果存在)
        """
        if not self.enabled or not self._redis:
            return None

        cache_key = self._generate_cache_key(provider, model, messages, temperature)

        try:
            with cache_latency.labels(operation="get").time():
                cached_json = await self._redis.get(cache_key)

            if cached_json:
                cache_hit_total.labels(provider=provider, model=model).inc()
                logger.debug(f"Cache hit: {cache_key}")
                return json.loads(cached_json)
            else:
                cache_miss_total.labels(provider=provider, model=model).inc()
                return None

        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    async def set(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        temperature: float = 0.7,
        ttl: Optional[int] = None,
        **kwargs,
    ):
        """
        设置缓存.

        Args:
            provider: 提供商
            model: 模型名称
            messages: 消息列表
            response: 响应数据
            temperature: 温度
            ttl: 过期时间(秒)
            **kwargs: 其他参数
        """
        if not self.enabled or not self._redis:
            return

        cache_key = self._generate_cache_key(provider, model, messages, temperature)
        ttl = ttl or self.default_ttl

        try:
            with cache_latency.labels(operation="set").time():
                response_json = json.dumps(response, ensure_ascii=False)
                await self._redis.setex(cache_key, ttl, response_json)

            cache_set_total.labels(provider=provider, model=model).inc()
            logger.debug(f"Cache set: {cache_key}, ttl={ttl}s")

        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    async def invalidate(self, pattern: str = "*"):
        """
        清除缓存.

        Args:
            pattern: 匹配模式
        """
        if not self.enabled or not self._redis:
            return

        try:
            keys = []
            async for key in self._redis.scan_iter(
                match=f"{self.key_prefix}:{pattern}",
                count=100,
            ):
                keys.append(key)

            if keys:
                await self._redis.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")

        except Exception as e:
            logger.warning(f"Cache invalidate error: {e}")

    async def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计.

        Returns:
            统计信息
        """
        if not self.enabled or not self._redis:
            return {
                "enabled": False,
                "total_entries": 0,
            }

        try:
            # 统计缓存键数量
            total_entries = 0
            async for _ in self._redis.scan_iter(
                match=f"{self.key_prefix}:*",
                count=100,
            ):
                total_entries += 1

            # 更新Gauge
            cache_size.set(total_entries)

            # Redis 内存信息
            info = await self._redis.info("memory")
            used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)

            return {
                "enabled": True,
                "total_entries": total_entries,
                "default_ttl_seconds": self.default_ttl,
                "redis_memory_mb": round(used_memory_mb, 2),
            }

        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
            return {"enabled": True, "error": str(e)}


# 全局缓存实例
_cache_instance: Optional[SemanticCache] = None


def get_cache() -> SemanticCache:
    """获取全局缓存实例."""
    global _cache_instance
    if _cache_instance is None:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return _cache_instance


def init_cache(
    redis_url: str = "redis://localhost:6379/0",
    ttl: int = 120,
    enabled: bool = True,
) -> SemanticCache:
    """
    初始化全局缓存.

    Args:
        redis_url: Redis连接URL
        ttl: 默认TTL(秒)
        enabled: 是否启用

    Returns:
        缓存实例
    """
    global _cache_instance
    _cache_instance = SemanticCache(
        redis_url=redis_url,
        default_ttl=ttl,
        enabled=enabled,
    )
    return _cache_instance
