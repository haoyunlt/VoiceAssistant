"""
LLM Cache Service - LLM调用结果缓存

降低LLM调用成本，提升响应速度
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class LLMCacheService:
    """LLM缓存服务"""

    def __init__(self, redis_client, ttl: int = 86400):
        """
        初始化缓存服务

        Args:
            redis_client: Redis客户端
            ttl: 缓存TTL（秒），默认24小时
        """
        self.redis = redis_client
        self.ttl = ttl
        self.hit_count = 0
        self.miss_count = 0

    def _generate_key(self, content: str, domain: str, operation: str) -> str:
        """
        生成缓存键

        Args:
            content: 内容文本
            domain: 领域
            operation: 操作类型

        Returns:
            缓存键
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"llm:{operation}:{content_hash}:{domain}"

    async def get_extraction_result(
        self, content: str, domain: str = "general"
    ) -> dict[str, Any] | None:
        """
        获取实体提取缓存结果

        Args:
            content: 文本内容
            domain: 领域

        Returns:
            缓存的提取结果，未命中返回None
        """
        try:
            key = self._generate_key(content, domain, "extract")
            cached = await self.redis.get(key)

            if cached:
                self.hit_count += 1
                logger.debug(f"Cache hit: {key[:50]}...")
                result = json.loads(cached)
                result["from_cache"] = True
                return result

            self.miss_count += 1
            logger.debug(f"Cache miss: {key[:50]}...")
            return None

        except Exception as e:
            logger.warning(f"Failed to get cache: {e}")
            return None

    async def set_extraction_result(
        self, content: str, domain: str, result: dict[str, Any]
    ) -> bool:
        """
        设置实体提取缓存

        Args:
            content: 文本内容
            domain: 领域
            result: 提取结果

        Returns:
            是否成功
        """
        try:
            key = self._generate_key(content, domain, "extract")

            # 添加元数据
            cache_data = {
                **result,
                "cached_at": datetime.now().isoformat(),
                "from_cache": False,
            }

            await self.redis.setex(key, self.ttl, json.dumps(cache_data))
            logger.debug(f"Cache set: {key[:50]}...")
            return True

        except Exception as e:
            logger.warning(f"Failed to set cache: {e}")
            return False

    async def get_query_entities(self, query: str) -> list[str] | None:
        """
        获取查询实体识别缓存

        Args:
            query: 查询文本

        Returns:
            实体列表，未命中返回None
        """
        try:
            key = self._generate_key(query, "general", "query_entities")
            cached = await self.redis.get(key)

            if cached:
                self.hit_count += 1
                return json.loads(cached)

            self.miss_count += 1
            return None

        except Exception as e:
            logger.warning(f"Failed to get query entities cache: {e}")
            return None

    async def set_query_entities(self, query: str, entities: list[str]) -> bool:
        """
        设置查询实体识别缓存

        Args:
            query: 查询文本
            entities: 实体列表

        Returns:
            是否成功
        """
        try:
            key = self._generate_key(query, "general", "query_entities")
            await self.redis.setex(key, self.ttl, json.dumps(entities))
            return True

        except Exception as e:
            logger.warning(f"Failed to set query entities cache: {e}")
            return False

    async def get_community_summary(self, community_id: str, domain: str) -> str | None:
        """
        获取社区摘要缓存

        Args:
            community_id: 社区ID
            domain: 领域

        Returns:
            摘要文本，未命中返回None
        """
        try:
            key = f"llm:summary:{community_id}:{domain}"
            cached = await self.redis.get(key)

            if cached:
                self.hit_count += 1
                return cached

            self.miss_count += 1
            return None

        except Exception as e:
            logger.warning(f"Failed to get community summary cache: {e}")
            return None

    async def set_community_summary(self, community_id: str, domain: str, summary: str) -> bool:
        """
        设置社区摘要缓存

        Args:
            community_id: 社区ID
            domain: 领域
            summary: 摘要文本

        Returns:
            是否成功
        """
        try:
            key = f"llm:summary:{community_id}:{domain}"
            # 社区摘要TTL更长（7天）
            await self.redis.setex(key, 7 * 86400, summary)
            return True

        except Exception as e:
            logger.warning(f"Failed to set community summary cache: {e}")
            return False

    async def invalidate_document_cache(self, document_id: str) -> int:
        """
        失效文档相关缓存

        Args:
            document_id: 文档ID

        Returns:
            删除的键数量
        """
        try:
            pattern = f"llm:*:*:{document_id}*"
            keys = []

            # 扫描匹配的键
            cursor = 0
            while True:
                cursor, batch = await self.redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            # 删除
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Invalidated {deleted} cache keys for document {document_id}")
                return deleted

            return 0

        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息
        """
        total = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total if total > 0 else 0.0

        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "total_requests": total,
            "hit_rate": hit_rate,
        }

    async def clear_stats(self):
        """清空统计信息"""
        self.hit_count = 0
        self.miss_count = 0


# 全局实例
_cache_service: LLMCacheService | None = None


def get_llm_cache_service(redis_client) -> LLMCacheService:
    """
    获取LLM缓存服务实例（单例）

    Args:
        redis_client: Redis客户端

    Returns:
        LLMCacheService实例
    """
    global _cache_service

    if _cache_service is None:
        _cache_service = LLMCacheService(redis_client)

    return _cache_service
