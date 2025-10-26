"""Redis 缓存"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 缓存客户端"""

    def __init__(
        self,
        host: str = "redis",
        port: int = 6379,
        db: int = 2,  # 使用 DB 2 用于检索缓存
        password: str = None,
    ):
        """
        初始化 Redis 客户端

        Args:
            host: Redis 主机
            port: Redis 端口
            db: 数据库编号
            password: 密码
        """
        self.host = host
        self.port = port
        self.db = db
        self.redis_client = None

        logger.info(f"Redis cache created: {host}:{port}, db={db}")

    async def initialize(self):
        """初始化连接"""
        self.redis_client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password if hasattr(self, "password") else None,
            decode_responses=False,  # 返回 bytes
        )

        # 测试连接
        await self.redis_client.ping()

        logger.info("Redis cache initialized")

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值（JSON 反序列化后）
        """
        if not self.redis_client:
            return None

        value = await self.redis_client.get(key)

        if value is None:
            return None

        # JSON 反序列化
        return json.loads(value)

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值（将被 JSON 序列化）
            ttl: 过期时间（秒）
        """
        if not self.redis_client:
            return

        # JSON 序列化
        serialized_value = json.dumps(value, ensure_ascii=False)

        # 设置缓存
        await self.redis_client.setex(key, ttl, serialized_value)

    async def delete(self, key: str):
        """删除缓存"""
        if not self.redis_client:
            return

        await self.redis_client.delete(key)

    async def cleanup(self):
        """清理资源"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis cache closed")
