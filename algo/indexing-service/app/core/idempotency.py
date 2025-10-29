"""幂等性管理 - 防止重复处理"""
import hashlib
import logging
import time

logger = logging.getLogger(__name__)


class IdempotencyManager:
    """
    幂等性管理器

    使用内存缓存实现（生产环境应使用Redis）
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        初始化

        Args:
            ttl_seconds: 幂等性键的TTL（秒）
        """
        self.ttl_seconds = ttl_seconds
        self.cache = {}  # key: {result, timestamp}
        self.processing = set()  # 正在处理的文档ID

        logger.info(f"Idempotency manager initialized with TTL={ttl_seconds}s")

    def generate_key(self, document_id: str, tenant_id: str) -> str:
        """
        生成幂等性键

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            幂等性键
        """
        data = f"{tenant_id}:{document_id}"
        return hashlib.sha256(data.encode()).hexdigest()

    def is_duplicate(self, document_id: str, tenant_id: str) -> bool:
        """
        检查是否为重复请求

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            是否重复
        """
        key = self.generate_key(document_id, tenant_id)

        # 清理过期的缓存
        self._cleanup_expired()

        # 检查是否在缓存中
        if key in self.cache:
            cache_entry = self.cache[key]
            timestamp = cache_entry["timestamp"]

            # 检查是否过期
            if time.time() - timestamp < self.ttl_seconds:
                logger.info(f"Duplicate request detected for document {document_id}")
                return True
            else:
                # 已过期，删除
                del self.cache[key]

        return False

    def is_processing(self, document_id: str, tenant_id: str) -> bool:
        """
        检查文档是否正在处理中

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            是否正在处理
        """
        key = self.generate_key(document_id, tenant_id)
        return key in self.processing

    def mark_processing(self, document_id: str, tenant_id: str):
        """
        标记文档为处理中

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
        """
        key = self.generate_key(document_id, tenant_id)
        self.processing.add(key)
        logger.debug(f"Marked document {document_id} as processing")

    def mark_completed(self, document_id: str, tenant_id: str, result: dict):
        """
        标记文档处理完成，并缓存结果

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
            result: 处理结果
        """
        key = self.generate_key(document_id, tenant_id)

        # 从处理中移除
        self.processing.discard(key)

        # 缓存结果
        self.cache[key] = {
            "result": result,
            "timestamp": time.time(),
        }

        logger.debug(f"Marked document {document_id} as completed and cached result")

    def mark_failed(self, document_id: str, tenant_id: str):
        """
        标记文档处理失败

        Args:
            document_id: 文档ID
            tenant_id: 租户ID
        """
        key = self.generate_key(document_id, tenant_id)

        # 从处理中移除（允许重试）
        self.processing.discard(key)

        logger.debug(f"Marked document {document_id} as failed")

    def get_cached_result(self, document_id: str, tenant_id: str) -> dict | None:
        """
        获取缓存的处理结果

        Args:
            document_id: 文档ID
            tenant_id: 租户ID

        Returns:
            缓存的结果，如果不存在则返回None
        """
        key = self.generate_key(document_id, tenant_id)

        if key in self.cache:
            cache_entry = self.cache[key]
            timestamp = cache_entry["timestamp"]

            # 检查是否过期
            if time.time() - timestamp < self.ttl_seconds:
                logger.info(f"Returning cached result for document {document_id}")
                return cache_entry["result"]
            else:
                # 已过期，删除
                del self.cache[key]

        return None

    def _cleanup_expired(self):
        """清理过期的缓存"""
        now = time.time()
        expired_keys = [
            key for key, value in self.cache.items()
            if now - value["timestamp"] > self.ttl_seconds
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get_stats(self) -> dict:
        """获取统计信息"""
        self._cleanup_expired()

        return {
            "cached_results": len(self.cache),
            "processing_count": len(self.processing),
            "ttl_seconds": self.ttl_seconds,
        }


# 全局单例
_idempotency_manager = None


def get_idempotency_manager() -> IdempotencyManager:
    """获取幂等性管理器单例"""
    global _idempotency_manager

    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager()

    return _idempotency_manager
