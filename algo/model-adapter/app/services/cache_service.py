"""请求缓存服务"""

import hashlib
import json

import redis

from app.core.config import settings
from app.core.logging import logger
from app.models.request import ChatRequest
from app.models.response import ChatResponse


class RequestCacheService:
    """请求缓存服务"""

    def __init__(self):
        """初始化"""
        # Redis连接
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

        # 缓存键前缀
        self.key_prefix = "model_adapter:cache"

        # 默认TTL（秒）
        self.default_ttl = 3600  # 1小时

        logger.info("Request cache service initialized")

    def _generate_cache_key(self, request: ChatRequest) -> str:
        """生成缓存键

        Args:
            request: 聊天请求

        Returns:
            缓存键
        """
        # 序列化请求（排除stream参数）
        request_dict = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
        }

        # 生成JSON字符串（确保顺序一致）
        request_str = json.dumps(request_dict, sort_keys=True, ensure_ascii=False)

        # 生成哈希
        hash_value = hashlib.sha256(request_str.encode()).hexdigest()

        return f"{self.key_prefix}:{hash_value}"

    async def get_cached_response(self, request: ChatRequest) -> ChatResponse | None:
        """获取缓存的响应

        Args:
            request: 聊天请求

        Returns:
            缓存的响应（如果存在）
        """
        # 流式请求不缓存
        if request.stream:
            return None

        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(request)

            # 从Redis获取
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                logger.info(f"Cache hit for request: {request.model}")

                # 解析JSON
                response_dict = json.loads(cached_data)

                # 转换为ChatResponse对象
                response = ChatResponse.parse_obj(response_dict)

                # 更新缓存访问时间（续期）
                self.redis_client.expire(cache_key, self.default_ttl)

                return response

            return None
        except Exception as e:
            logger.error(f"Error getting cached response: {e}")
            return None

    async def set_cached_response(
        self, request: ChatRequest, response: ChatResponse, ttl: int | None = None
    ):
        """设置缓存响应

        Args:
            request: 聊天请求
            response: 聊天响应
            ttl: 过期时间（秒）
        """
        # 流式请求不缓存
        if request.stream:
            return

        try:
            if ttl is None:
                ttl = self.default_ttl

            # 生成缓存键
            cache_key = self._generate_cache_key(request)

            # 序列化响应
            response_dict = response.dict()
            response_json = json.dumps(response_dict, ensure_ascii=False)

            # 保存到Redis
            self.redis_client.setex(cache_key, ttl, response_json)

            logger.info(f"Cached response for request: {request.model}")
        except Exception as e:
            logger.error(f"Error setting cached response: {e}")

    async def invalidate_cache(self, pattern: str = "*"):
        """清除缓存

        Args:
            pattern: 匹配模式
        """
        try:
            # 扫描匹配的键
            keys = []
            cursor = 0

            while True:
                cursor, partial_keys = self.redis_client.scan(
                    cursor, match=f"{self.key_prefix}:{pattern}", count=100
                )
                keys.extend(partial_keys)

                if cursor == 0:
                    break

            # 删除键
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    async def get_cache_stats(self) -> dict:
        """获取缓存统计信息

        Returns:
            统计信息字典
        """
        try:
            # 扫描所有缓存键
            keys = []
            cursor = 0

            while True:
                cursor, partial_keys = self.redis_client.scan(
                    cursor, match=f"{self.key_prefix}:*", count=100
                )
                keys.extend(partial_keys)

                if cursor == 0:
                    break

            # 统计TTL分布
            ttl_distribution = {"< 1h": 0, "1h - 6h": 0, "6h - 24h": 0, "> 24h": 0}

            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl < 0:
                    continue

                if ttl < 3600:
                    ttl_distribution["< 1h"] += 1
                elif ttl < 21600:
                    ttl_distribution["1h - 6h"] += 1
                elif ttl < 86400:
                    ttl_distribution["6h - 24h"] += 1
                else:
                    ttl_distribution["> 24h"] += 1

            return {
                "total_entries": len(keys),
                "ttl_distribution": ttl_distribution,
                "default_ttl_seconds": self.default_ttl,
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
