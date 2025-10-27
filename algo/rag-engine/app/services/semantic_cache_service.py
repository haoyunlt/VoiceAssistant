"""语义缓存服务"""
import hashlib
import json
from typing import Optional

import numpy as np
import redis
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import logger


class CachedAnswer(BaseModel):
    """缓存的答案"""
    answer: str
    similarity: float
    original_query: str
    sources: list = []


class SemanticCacheService:
    """语义缓存服务"""

    def __init__(self):
        """初始化"""
        # Redis连接
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )

        # 加载轻量级embedding模型
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

        # 相似度阈值
        self.similarity_threshold = 0.9

        # 缓存TTL（秒）
        self.cache_ttl = 3600  # 1小时

        # 最大缓存查询数
        self.max_cache_queries = 1000

        logger.info("Semantic cache service initialized")

    async def get_cached_answer(
        self,
        query: str
    ) -> Optional[CachedAnswer]:
        """获取缓存的答案

        Args:
            query: 查询文本

        Returns:
            缓存的答案（如果命中）
        """
        try:
            # 1. 计算query embedding
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)

            # 2. 从Redis获取所有缓存的查询
            cached_queries = self._get_all_cached_queries()

            if not cached_queries:
                return None

            # 3. 计算相似度
            best_match = None
            best_similarity = 0.0

            for cached_query_id, cached_data in cached_queries.items():
                try:
                    cached_embedding = np.array(cached_data["embedding"])

                    # 余弦相似度
                    similarity = float(np.dot(query_embedding, cached_embedding))

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = {
                            "id": cached_query_id,
                            "query": cached_data["query"],
                            "similarity": similarity
                        }
                except Exception as e:
                    logger.warning(f"Error computing similarity for {cached_query_id}: {e}")
                    continue

            # 4. 检查是否超过阈值
            if best_match and best_similarity >= self.similarity_threshold:
                # 命中缓存，获取答案
                cache_id = best_match["id"]
                cached_answer = self.redis_client.get(f"semantic_cache:{cache_id}")

                if cached_answer:
                    answer_data = json.loads(cached_answer)

                    # 更新缓存访问时间（续期）
                    self.redis_client.expire(f"semantic_cache:{cache_id}", self.cache_ttl)
                    self.redis_client.expire(f"semantic_cache:query:{cache_id}", self.cache_ttl)

                    return CachedAnswer(
                        answer=answer_data["answer"],
                        similarity=best_similarity,
                        original_query=best_match["query"],
                        sources=answer_data.get("sources", [])
                    )

            return None
        except Exception as e:
            logger.error(f"Error getting cached answer: {e}")
            return None

    async def set_cached_answer(
        self,
        query: str,
        answer: str,
        sources: list = None,
        ttl: int = None
    ):
        """设置缓存答案

        Args:
            query: 查询文本
            answer: 答案
            sources: 来源文档
            ttl: 过期时间（秒）
        """
        try:
            if ttl is None:
                ttl = self.cache_ttl

            # 1. 计算query embedding
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)

            # 2. 生成缓存ID
            cache_id = self._generate_cache_id(query)

            # 3. 保存答案到Redis
            answer_data = {
                "answer": answer,
                "sources": sources or []
            }
            self.redis_client.setex(
                f"semantic_cache:{cache_id}",
                ttl,
                json.dumps(answer_data, ensure_ascii=False)
            )

            # 4. 保存query和embedding
            query_data = {
                "query": query,
                "embedding": query_embedding.tolist()
            }
            self.redis_client.setex(
                f"semantic_cache:query:{cache_id}",
                ttl,
                json.dumps(query_data)
            )

            # 5. 检查缓存数量，超过限制则清理最旧的
            await self._check_and_cleanup()

            logger.info(f"Cached answer for query: {query[:50]}...")
        except Exception as e:
            logger.error(f"Error setting cached answer: {e}")

    def _get_all_cached_queries(self) -> dict:
        """获取所有缓存的查询"""
        cached_queries = {}

        # 扫描所有query keys
        cursor = 0
        while True:
            cursor, keys = self.redis_client.scan(
                cursor,
                match="semantic_cache:query:*",
                count=100
            )

            for key in keys:
                try:
                    query_data = self.redis_client.get(key)
                    if query_data:
                        cache_id = key.replace("semantic_cache:query:", "")
                        cached_queries[cache_id] = json.loads(query_data)
                except Exception as e:
                    logger.warning(f"Error loading cached query {key}: {e}")

            if cursor == 0:
                break

        return cached_queries

    def _generate_cache_id(self, query: str) -> str:
        """生成缓存ID"""
        return hashlib.md5(query.encode()).hexdigest()

    async def _check_and_cleanup(self):
        """检查并清理超出限制的缓存"""
        try:
            # 获取所有query keys数量
            query_keys = list(self.redis_client.scan_iter(match="semantic_cache:query:*"))

            if len(query_keys) > self.max_cache_queries:
                # 超出限制，删除最旧的10%
                to_delete = int(len(query_keys) * 0.1)

                # 按TTL排序（TTL越短越旧）
                keys_with_ttl = []
                for key in query_keys:
                    ttl = self.redis_client.ttl(key)
                    if ttl > 0:
                        keys_with_ttl.append((key, ttl))

                keys_with_ttl.sort(key=lambda x: x[1])

                # 删除最旧的
                for key, _ in keys_with_ttl[:to_delete]:
                    cache_id = key.replace("semantic_cache:query:", "")
                    self.redis_client.delete(key)
                    self.redis_client.delete(f"semantic_cache:{cache_id}")

                logger.info(f"Cleaned up {to_delete} oldest cache entries")
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")

    async def clear_cache(self):
        """清空所有缓存"""
        try:
            # 删除所有semantic_cache keys
            keys = list(self.redis_client.scan_iter(match="semantic_cache:*"))
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    async def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        try:
            query_keys = list(self.redis_client.scan_iter(match="semantic_cache:query:*"))
            answer_keys = list(self.redis_client.scan_iter(match="semantic_cache:*"))

            # 排除query keys
            answer_keys = [k for k in answer_keys if not k.startswith("semantic_cache:query:")]

            return {
                "total_queries": len(query_keys),
                "total_answers": len(answer_keys),
                "max_capacity": self.max_cache_queries,
                "usage_percentage": round(len(query_keys) / self.max_cache_queries * 100, 2),
                "ttl_seconds": self.cache_ttl,
                "similarity_threshold": self.similarity_threshold
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
