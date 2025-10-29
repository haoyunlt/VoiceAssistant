"""Redis 缓存"""

import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 缓存客户端"""

    def __init__(
        self,
        host: str = "redis",
        port: int = 6379,
        db: int = 2,  # 使用 DB 2 用于检索缓存
        password: str | None = None,
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
        self.password = password  # Fix: 保存password参数
        self.redis_client = None

        logger.info(f"Redis cache created: {host}:{port}, db={db}")

    async def initialize(self) -> None:
        """初始化连接"""
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False,  # 返回 bytes
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )

            # 测试连接
            await self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            raise

    async def get(self, key: str) -> Any | None:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值（JSON 反序列化后）
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return None

        try:
            value = await self.redis_client.get(key)

            if value is None:
                return None

            # JSON 反序列化
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached value for key {key}: {e}")
            # 删除损坏的缓存
            await self.delete(key)
            return None
        except Exception as e:
            logger.error(f"Error getting cache for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值（将被 JSON 序列化）
            ttl: 过期时间（秒）
        """
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return

        try:
            # JSON 序列化
            serialized_value = json.dumps(value, ensure_ascii=False)

            # 设置缓存
            await self.redis_client.setex(key, ttl, serialized_value)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value for key {key}: {e}")
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {e}")

    async def delete(self, key: str) -> None:
        """删除缓存"""
        if not self.redis_client:
            return

        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {e}")

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.redis_client:
            return False

        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking key existence {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """获取键的剩余过期时间（秒）"""
        if not self.redis_client:
            return -2

        try:
            return await self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -2

    async def cleanup(self) -> None:
        """清理资源"""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis cache closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
