"""语义缓存服务 v2.0 - FAISS 优化版"""

import hashlib
import json
import time
from typing import Any

import numpy as np
import redis
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

import logging

logger = logging.getLogger(__name__)


class CachedAnswer(BaseModel):
    """缓存的答案"""

    answer: str
    similarity: float
    original_query: str
    sources: list = []


class SemanticCacheService:
    """语义缓存服务 v2.0 - 使用 FAISS 加速向量相似度检索"""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        embedding_model: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.92,
        cache_ttl: int = 3600,
        max_cache_queries: int = 10000,
        use_faiss: bool = True,
    ):
        """初始化

        Args:
            redis_host: Redis 主机
            redis_port: Redis 端口
            redis_db: Redis 数据库
            embedding_model: Embedding 模型名称
            similarity_threshold: 相似度阈值（提高到 0.92）
            cache_ttl: 缓存 TTL（秒）
            max_cache_queries: 最大缓存查询数（提升到 10000）
            use_faiss: 是否使用 FAISS（推荐）
        """
        # Redis连接
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True,
        )

        # 加载轻量级embedding模型
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()

        # 相似度阈值
        self.similarity_threshold = similarity_threshold

        # 缓存TTL（秒）
        self.cache_ttl = cache_ttl

        # 最大缓存查询数
        self.max_cache_queries = max_cache_queries

        # FAISS 索引
        self.use_faiss = use_faiss and FAISS_AVAILABLE
        self.faiss_index = None
        self.cache_id_mapping = []  # ID 映射列表

        if self.use_faiss:
            self._initialize_faiss()
            logger.info(f"Semantic cache service initialized with FAISS (dim={self.embedding_dim})")
        else:
            logger.info("Semantic cache service initialized (FAISS disabled)")

        # 统计信息
        self.stats = {
            "hits": 0,
            "misses": 0,
            "total_queries": 0,
            "avg_latency_ms": 0,
            "total_latency_ms": 0,
        }

    def _initialize_faiss(self):
        """初始化 FAISS 索引"""
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available. Install with: pip install faiss-cpu")
            self.use_faiss = False
            return

        try:
            # 使用内积（Inner Product）索引，适用于已归一化的向量（余弦相似度）
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            logger.info(f"FAISS index initialized: IndexFlatIP with dimension {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS: {e}")
            self.use_faiss = False

    async def get_cached_answer(self, query: str) -> CachedAnswer | None:
        """获取缓存的答案（FAISS 优化版）

        Args:
            query: 查询文本

        Returns:
            缓存的答案（如果命中）
        """
        start_time = time.time()
        self.stats["total_queries"] += 1

        try:
            # 1. 计算 query embedding（归一化，用于余弦相似度）
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)
            query_embedding = query_embedding.astype("float32").reshape(1, -1)

            # 2. 使用 FAISS 或遍历查找最相似的缓存
            if self.use_faiss and self.faiss_index and self.faiss_index.ntotal > 0:
                # FAISS 快速检索
                similarities, indices = self.faiss_index.search(query_embedding, k=1)
                best_similarity = float(similarities[0][0])
                best_idx = int(indices[0][0])

                if best_similarity >= self.similarity_threshold and best_idx < len(
                    self.cache_id_mapping
                ):
                    cache_id = self.cache_id_mapping[best_idx]
                    best_match = {"id": cache_id, "similarity": best_similarity}
                else:
                    best_match = None
            else:
                # 回退到遍历方式
                best_match = await self._find_best_match_linear(query_embedding[0])

            # 3. 检查是否命中
            if best_match:
                cache_id = best_match["id"]
                cached_answer = self.redis_client.get(f"semantic_cache:{cache_id}")

                if cached_answer:
                    answer_data = json.loads(cached_answer)

                    # 获取原始查询
                    query_data = self.redis_client.get(f"semantic_cache:query:{cache_id}")
                    original_query = json.loads(query_data)["query"] if query_data else ""

                    # 更新缓存访问时间（续期）
                    self.redis_client.expire(f"semantic_cache:{cache_id}", self.cache_ttl)
                    self.redis_client.expire(f"semantic_cache:query:{cache_id}", self.cache_ttl)

                    # 更新统计
                    latency_ms = (time.time() - start_time) * 1000
                    self.stats["hits"] += 1
                    self.stats["total_latency_ms"] += latency_ms
                    self.stats["avg_latency_ms"] = (
                        self.stats["total_latency_ms"] / self.stats["total_queries"]
                    )

                    logger.info(
                        f"Cache HIT: similarity={best_match['similarity']:.4f}, latency={latency_ms:.2f}ms"
                    )

                    return CachedAnswer(
                        answer=answer_data["answer"],
                        similarity=best_match["similarity"],
                        original_query=original_query,
                        sources=answer_data.get("sources", []),
                    )

            # 未命中
            self.stats["misses"] += 1
            latency_ms = (time.time() - start_time) * 1000
            self.stats["total_latency_ms"] += latency_ms
            self.stats["avg_latency_ms"] = (
                self.stats["total_latency_ms"] / self.stats["total_queries"]
            )

            logger.debug(f"Cache MISS: latency={latency_ms:.2f}ms")
            return None

        except Exception as e:
            logger.error(f"Error getting cached answer: {e}")
            self.stats["misses"] += 1
            return None

    async def _find_best_match_linear(
        self, query_embedding: np.ndarray
    ) -> dict[str, Any] | None:
        """线性搜索最佳匹配（回退方案）"""
        cached_queries = self._get_all_cached_queries()

        if not cached_queries:
            return None

        best_match = None
        best_similarity = 0.0

        for cached_query_id, cached_data in cached_queries.items():
            try:
                cached_embedding = np.array(cached_data["embedding"], dtype="float32")
                similarity = float(np.dot(query_embedding, cached_embedding))

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {"id": cached_query_id, "similarity": similarity}
            except Exception as e:
                logger.warning(f"Error computing similarity for {cached_query_id}: {e}")
                continue

        if best_match and best_similarity >= self.similarity_threshold:
            return best_match
        return None

    async def set_cached_answer(
        self, query: str, answer: str, sources: list = None, ttl: int = None
    ):
        """设置缓存答案（FAISS 优化版）

        Args:
            query: 查询文本
            answer: 答案
            sources: 来源文档
            ttl: 过期时间（秒）
        """
        try:
            if ttl is None:
                ttl = self.cache_ttl

            # 1. 计算 query embedding（归一化）
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)

            # 2. 生成缓存 ID
            cache_id = self._generate_cache_id(query)

            # 3. 保存答案到 Redis
            answer_data = {
                "answer": answer,
                "sources": sources or [],
                "timestamp": time.time(),
            }
            self.redis_client.setex(
                f"semantic_cache:{cache_id}", ttl, json.dumps(answer_data, ensure_ascii=False)
            )

            # 4. 保存 query 和 embedding
            query_data = {
                "query": query,
                "embedding": query_embedding.tolist(),
                "timestamp": time.time(),
            }
            self.redis_client.setex(f"semantic_cache:query:{cache_id}", ttl, json.dumps(query_data))

            # 5. 更新 FAISS 索引
            if self.use_faiss and self.faiss_index is not None:
                embedding_array = query_embedding.astype("float32").reshape(1, -1)
                self.faiss_index.add(embedding_array)
                self.cache_id_mapping.append(cache_id)

            # 6. 检查缓存数量，超过限制则清理最旧的
            await self._check_and_cleanup()

            logger.info(
                f"Cached answer for query: {query[:50]}... (FAISS indexed: {self.use_faiss})"
            )
        except Exception as e:
            logger.error(f"Error setting cached answer: {e}")

    def _get_all_cached_queries(self) -> dict:
        """获取所有缓存的查询"""
        cached_queries = {}

        # 扫描所有query keys
        cursor = 0
        while True:
            cursor, keys = self.redis_client.scan(cursor, match="semantic_cache:query:*", count=100)

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

    async def rebuild_faiss_index(self):
        """重建 FAISS 索引（用于启动时加载或定期重建）"""
        if not self.use_faiss:
            logger.warning("FAISS is disabled, skipping index rebuild")
            return

        try:
            logger.info("Rebuilding FAISS index from Redis...")

            # 重新初始化索引
            self._initialize_faiss()
            self.cache_id_mapping = []

            # 加载所有缓存的查询向量
            cached_queries = self._get_all_cached_queries()

            if not cached_queries:
                logger.info("No cached queries to index")
                return

            embeddings = []
            cache_ids = []

            for cache_id, query_data in cached_queries.items():
                try:
                    embedding = np.array(query_data["embedding"], dtype="float32")
                    embeddings.append(embedding)
                    cache_ids.append(cache_id)
                except Exception as e:
                    logger.warning(f"Failed to load embedding for {cache_id}: {e}")
                    continue

            if embeddings:
                # 批量添加到 FAISS
                embeddings_array = np.array(embeddings, dtype="float32")
                self.faiss_index.add(embeddings_array)
                self.cache_id_mapping = cache_ids

                logger.info(f"FAISS index rebuilt: {len(cache_ids)} vectors indexed")
            else:
                logger.warning("No valid embeddings found for indexing")

        except Exception as e:
            logger.error(f"Failed to rebuild FAISS index: {e}", exc_info=True)

    async def get_cache_stats(self) -> dict:
        """获取缓存统计信息（增强版）"""
        try:
            query_keys = list(self.redis_client.scan_iter(match="semantic_cache:query:*"))
            answer_keys = list(self.redis_client.scan_iter(match="semantic_cache:*"))

            # 排除 query keys
            answer_keys = [k for k in answer_keys if not k.startswith("semantic_cache:query:")]

            # 计算命中率
            hit_rate = 0.0
            if self.stats["total_queries"] > 0:
                hit_rate = self.stats["hits"] / self.stats["total_queries"]

            return {
                "total_queries": len(query_keys),
                "total_answers": len(answer_keys),
                "max_capacity": self.max_cache_queries,
                "usage_percentage": round(len(query_keys) / self.max_cache_queries * 100, 2),
                "ttl_seconds": self.cache_ttl,
                "similarity_threshold": self.similarity_threshold,
                "faiss_enabled": self.use_faiss,
                "faiss_indexed_count": self.faiss_index.ntotal
                if self.use_faiss and self.faiss_index
                else 0,
                # 运行时统计
                "runtime_stats": {
                    "total_queries": self.stats["total_queries"],
                    "hits": self.stats["hits"],
                    "misses": self.stats["misses"],
                    "hit_rate": round(hit_rate * 100, 2),
                    "avg_latency_ms": round(self.stats["avg_latency_ms"], 2),
                },
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
