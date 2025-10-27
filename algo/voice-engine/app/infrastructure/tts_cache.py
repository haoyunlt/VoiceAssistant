"""
TTS Redis 缓存

提供基于 Redis 的 TTS 缓存功能：
- LRU 淘汰策略
- 统计信息
- 缓存大小限制
"""

import base64
import hashlib
import time
from datetime import timedelta
from typing import Optional

import redis
import logging

logger = logging.getLogger(__name__)


class TTSRedisCache:
    """TTS Redis 缓存"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        ttl_days: int = 30,
        max_cache_size_mb: int = 1000,
    ):
        """
        初始化 TTS Redis 缓存

        Args:
            redis_url: Redis 连接 URL
            ttl_days: 缓存过期时间（天）
            max_cache_size_mb: 最大缓存大小（MB）
        """
        try:
            self.redis = redis.from_url(redis_url, decode_responses=False)
            # 测试连接
            self.redis.ping()
            logger.info(f"Connected to Redis: {redis_url}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Falling back to in-memory cache")
            self.redis = None
            self.memory_cache = {}

        self.ttl = timedelta(days=ttl_days)
        self.max_cache_size = max_cache_size_mb * 1024 * 1024  # 转为字节

    def _generate_key(
        self, text: str, voice: str, rate: str, pitch: str, format: str
    ) -> str:
        """
        生成缓存键

        Args:
            text: 文本
            voice: 音色
            rate: 语速
            pitch: 音调
            format: 格式

        Returns:
            缓存键（MD5 哈希）
        """
        cache_input = f"{text}:{voice}:{rate}:{pitch}:{format}"
        hash_key = hashlib.sha256(cache_input.encode()).hexdigest()
        return f"tts:cache:{hash_key}"

    def get(
        self,
        text: str,
        voice: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        format: str = "mp3",
    ) -> Optional[bytes]:
        """
        获取缓存

        Args:
            text: 文本
            voice: 音色
            rate: 语速
            pitch: 音调
            format: 格式

        Returns:
            音频数据（字节），如果不存在返回 None
        """
        if not self.redis:
            # 内存缓存降级
            key = self._generate_key(text, voice, rate, pitch, format)
            cached = self.memory_cache.get(key)
            if cached:
                return base64.b64decode(cached)
            return None

        key = self._generate_key(text, voice, rate, pitch, format)

        try:
            cached = self.redis.get(key)

            if cached:
                # 更新访问统计
                stats_key = f"{key}:stats"
                self.redis.hincrby(stats_key, "hits", 1)
                self.redis.hset(stats_key, "last_accessed", int(time.time()))

                # 刷新 TTL
                self.redis.expire(key, self.ttl)
                self.redis.expire(stats_key, self.ttl)

                # 更新 LRU 时间戳
                self.redis.zadd("tts:lru", {key: time.time()})

                logger.debug(f"Cache hit: {key[:16]}...")
                return cached

            logger.debug(f"Cache miss: {key[:16]}...")
            return None

        except redis.RedisError as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(
        self,
        text: str,
        voice: str,
        rate: str,
        pitch: str,
        format: str,
        audio_data: bytes,
    ):
        """
        设置缓存

        Args:
            text: 文本
            voice: 音色
            rate: 语速
            pitch: 音调
            format: 格式
            audio_data: 音频数据
        """
        if not self.redis:
            # 内存缓存降级
            key = self._generate_key(text, voice, rate, pitch, format)
            self.memory_cache[key] = base64.b64encode(audio_data).decode()
            return

        key = self._generate_key(text, voice, rate, pitch, format)
        audio_size = len(audio_data)

        try:
            # 检查缓存大小，必要时淘汰
            current_size = self._get_total_cache_size()
            if current_size + audio_size > self.max_cache_size:
                logger.warning(
                    f"Cache size ({current_size / 1024 / 1024:.2f} MB) "
                    f"exceeds limit ({self.max_cache_size / 1024 / 1024:.2f} MB), "
                    f"evicting LRU entries..."
                )
                self._evict_lru(audio_size)

            # 存储音频数据
            self.redis.setex(key, self.ttl, audio_data)

            # 存储元数据
            stats_key = f"{key}:stats"
            self.redis.hmset(
                stats_key,
                {
                    "text_length": len(text),
                    "audio_size": audio_size,
                    "created_at": int(time.time()),
                    "hits": 0,
                    "last_accessed": int(time.time()),
                },
            )
            self.redis.expire(stats_key, self.ttl)

            # 添加到 LRU 列表
            self.redis.zadd("tts:lru", {key: time.time()})

            logger.debug(
                f"Cache set: {key[:16]}... "
                f"(size: {audio_size / 1024:.2f} KB, "
                f"text_len: {len(text)})"
            )

        except redis.RedisError as e:
            logger.error(f"Redis set error: {e}")

    def _get_total_cache_size(self) -> int:
        """
        获取总缓存大小

        Returns:
            总大小（字节）
        """
        if not self.redis:
            return 0

        try:
            total = 0
            # 扫描所有缓存键（不包括 stats 和 lru）
            for key in self.redis.scan_iter("tts:cache:*"):
                if not key.endswith(b":stats"):
                    size = self.redis.memory_usage(key)
                    if size:
                        total += size
            return total

        except redis.RedisError as e:
            logger.error(f"Failed to get cache size: {e}")
            return 0

    def _evict_lru(self, needed_size: int):
        """
        LRU 淘汰

        Args:
            needed_size: 需要的空间（字节）
        """
        if not self.redis:
            return

        try:
            evicted_size = 0
            evicted_count = 0

            # 按时间戳升序获取（最久未使用）
            lru_keys = self.redis.zrange("tts:lru", 0, -1)

            for key in lru_keys:
                if evicted_size >= needed_size:
                    break

                # 获取大小
                stats_key = f"{key}:stats"
                size = self.redis.hget(stats_key, "audio_size")

                if size:
                    size = int(size)
                else:
                    # 如果 stats 不存在，估算大小
                    size = self.redis.memory_usage(key) or 0

                # 删除缓存
                self.redis.delete(key)
                self.redis.delete(stats_key)
                self.redis.zrem("tts:lru", key)

                evicted_size += size
                evicted_count += 1

            logger.info(
                f"🗑️  LRU evicted: {evicted_count} entries, "
                f"{evicted_size / 1024 / 1024:.2f} MB freed"
            )

        except redis.RedisError as e:
            logger.error(f"LRU eviction failed: {e}")

    def get_stats(self) -> dict:
        """
        获取缓存统计

        Returns:
            统计信息字典
        """
        if not self.redis:
            return {
                "backend": "memory",
                "total_entries": len(self.memory_cache),
                "total_size_mb": 0,
                "total_hits": 0,
                "hit_rate": 0,
            }

        try:
            # 扫描所有缓存键
            cache_keys = []
            for key in self.redis.scan_iter("tts:cache:*"):
                if not key.endswith(b":stats"):
                    cache_keys.append(key)

            total_entries = len(cache_keys)

            if total_entries == 0:
                return {
                    "backend": "redis",
                    "total_entries": 0,
                    "total_size_mb": 0,
                    "total_hits": 0,
                    "hit_rate": 0,
                    "avg_audio_size_kb": 0,
                }

            # 计算总大小
            total_size = sum(
                self.redis.memory_usage(k) or 0 for k in cache_keys
            )

            # 计算总命中数
            total_hits = 0
            total_audio_size = 0

            for key in cache_keys:
                stats_key = f"{key}:stats"
                hits = self.redis.hget(stats_key, "hits")
                audio_size = self.redis.hget(stats_key, "audio_size")

                if hits:
                    total_hits += int(hits)
                if audio_size:
                    total_audio_size += int(audio_size)

            # 计算命中率（命中数 / 总条目数）
            hit_rate = total_hits / max(total_entries, 1)

            return {
                "backend": "redis",
                "total_entries": total_entries,
                "total_size_mb": total_size / 1024 / 1024,
                "total_audio_size_mb": total_audio_size / 1024 / 1024,
                "total_hits": total_hits,
                "hit_rate": f"{hit_rate:.2f}",
                "avg_audio_size_kb": (
                    total_audio_size / total_entries / 1024
                    if total_entries > 0
                    else 0
                ),
                "max_cache_size_mb": self.max_cache_size / 1024 / 1024,
                "ttl_days": self.ttl.days,
            }

        except redis.RedisError as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "backend": "redis",
                "error": str(e),
            }

    def clear(self):
        """清空缓存"""
        if not self.redis:
            self.memory_cache.clear()
            logger.info("Memory cache cleared")
            return

        try:
            # 删除所有缓存键
            deleted = 0
            for key in self.redis.scan_iter("tts:cache:*"):
                self.redis.delete(key)
                deleted += 1

            # 清空 LRU 列表
            self.redis.delete("tts:lru")

            logger.info(f"Redis cache cleared: {deleted} keys deleted")

        except redis.RedisError as e:
            logger.error(f"Failed to clear cache: {e}")

    def delete(self, key: str):
        """
        删除指定缓存

        Args:
            key: 缓存键
        """
        if not self.redis:
            self.memory_cache.pop(key, None)
            return

        try:
            self.redis.delete(key)
            self.redis.delete(f"{key}:stats")
            self.redis.zrem("tts:lru", key)

            logger.debug(f"Cache deleted: {key[:16]}...")

        except redis.RedisError as e:
            logger.error(f"Failed to delete cache: {e}")

    def health_check(self) -> dict:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not self.redis:
            return {
                "healthy": True,
                "backend": "memory",
                "message": "Using in-memory cache (Redis not available)",
            }

        try:
            # 测试 Redis 连接
            self.redis.ping()

            return {
                "healthy": True,
                "backend": "redis",
                "message": "Redis connection OK",
            }

        except redis.RedisError as e:
            return {
                "healthy": False,
                "backend": "redis",
                "error": str(e),
            }
