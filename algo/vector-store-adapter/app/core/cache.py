"""Vector search cache implementation using Redis"""

import json
import logging

import xxhash

logger = logging.getLogger(__name__)


class VectorSearchCache:
    """
    Cache for vector search results using Redis

    Features:
    - Fast hashing using xxhash
    - Configurable TTL
    - Cache invalidation by collection/document
    - Hit/miss metrics tracking
    """

    def __init__(
        self,
        redis_client,
        ttl_seconds: int = 300,
        key_prefix: str = "vs_cache",
        enabled: bool = True,
    ):
        """
        Initialize cache

        Args:
            redis_client: Redis async client
            ttl_seconds: Cache TTL in seconds (default: 5 minutes)
            key_prefix: Redis key prefix
            enabled: Enable/disable cache
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.key_prefix = key_prefix
        self.enabled = enabled

    def _hash_vector(self, vector: list[float]) -> str:
        """
        Fast hash for vector using xxhash

        Args:
            vector: Query vector

        Returns:
            Hex hash string
        """
        # Convert to bytes and hash
        vector_bytes = str(vector).encode("utf-8")
        return xxhash.xxh64(vector_bytes).hexdigest()

    def _hash_filters(self, filters: dict | str | None) -> str:
        """
        Hash filters

        Args:
            filters: Filter conditions

        Returns:
            Hex hash string
        """
        if filters is None:
            return "none"
        filter_bytes = str(filters).encode("utf-8")
        return xxhash.xxh64(filter_bytes).hexdigest()

    def get_cache_key(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        tenant_id: str | None = None,
        filters: dict | str | None = None,
        backend: str = "milvus",
    ) -> str:
        """
        Generate cache key

        Args:
            collection: Collection name
            query_vector: Query vector
            top_k: Number of results
            tenant_id: Tenant ID
            filters: Filter conditions
            backend: Backend type

        Returns:
            Redis cache key
        """
        vector_hash = self._hash_vector(query_vector)
        filter_hash = self._hash_filters(filters)
        tenant_part = f":{tenant_id}" if tenant_id else ""

        return f"{self.key_prefix}:{backend}:{collection}:{top_k}{tenant_part}:{vector_hash}:{filter_hash}"

    async def get(self, cache_key: str) -> list[dict] | None:
        """
        Get cached results

        Args:
            cache_key: Cache key

        Returns:
            Cached results or None if not found
        """
        if not self.enabled or not self.redis:
            return None

        try:
            data = await self.redis.get(cache_key)
            if data:
                logger.debug(f"Cache hit: {cache_key}")
                return json.loads(data)
            logger.debug(f"Cache miss: {cache_key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, cache_key: str, results: list[dict]) -> bool:
        """
        Set cache

        Args:
            cache_key: Cache key
            results: Search results

        Returns:
            Success status
        """
        if not self.enabled or not self.redis:
            return False

        try:
            data = json.dumps(results)
            await self.redis.setex(cache_key, self.ttl, data)
            logger.debug(f"Cache set: {cache_key} (TTL: {self.ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate_collection(self, collection: str, backend: str = "milvus") -> int:
        """
        Invalidate all cache entries for a collection

        Args:
            collection: Collection name
            backend: Backend type

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0

        try:
            pattern = f"{self.key_prefix}:{backend}:{collection}:*"
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += await self.redis.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Invalidated {deleted} cache entries for collection {collection}")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0

    async def invalidate_document(
        self, collection: str, _document_id: str, backend: str = "milvus"
    ) -> int:
        """
        Invalidate cache entries that may contain a document

        Note: This is a conservative approach that invalidates the entire collection
        since we don't track which cache entries contain which documents.

        Args:
            collection: Collection name
            document_id: Document ID
            backend: Backend type

        Returns:
            Number of keys deleted
        """
        # For simplicity, invalidate entire collection
        # In production, you might want to track document->cache_key mapping
        return await self.invalidate_collection(collection, backend)

    async def clear_all(self) -> int:
        """
        Clear all cache entries

        Returns:
            Number of keys deleted
        """
        if not self.enabled or not self.redis:
            return 0

        try:
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += await self.redis.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Cleared {deleted} cache entries")
            return deleted
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    async def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Cache stats dict
        """
        if not self.enabled or not self.redis:
            return {
                "enabled": False,
            }

        try:
            # Count total keys
            pattern = f"{self.key_prefix}:*"
            cursor = 0
            total_keys = 0

            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                total_keys += len(keys)
                if cursor == 0:
                    break

            return {
                "enabled": True,
                "ttl_seconds": self.ttl,
                "total_keys": total_keys,
                "key_prefix": self.key_prefix,
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {
                "enabled": True,
                "error": str(e),
            }
