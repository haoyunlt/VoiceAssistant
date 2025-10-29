"""
Embedding服务

提供文本向量化和相似度计算功能:
- 支持多种Embedding模型
- 批量向量化
- 相似度计算
- 向量缓存
"""
import asyncio
import logging
import os
import time

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embedding服务"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
        cache_enabled: bool = True,
        batch_size: int = 32
    ):
        """
        初始化Embedding服务

        Args:
            model_name: 模型名称
            device: 设备 (cpu/cuda)
            cache_enabled: 是否启用缓存
            batch_size: 批处理大小
        """
        self.model_name = model_name
        self.device = device
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size

        # 延迟加载模型
        self.model: SentenceTransformer | None = None
        self._model_loaded = False

        # 缓存
        self.cache: dict[str, np.ndarray] = {}
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(
            f"EmbeddingService initialized: "
            f"model={model_name}, device={device}, cache={cache_enabled}"
        )

    async def initialize(self):
        """初始化模型（异步）"""
        if self._model_loaded:
            return

        try:
            logger.info(f"Loading embedding model: {self.model_name}")

            # 在线程池中加载模型（避免阻塞事件循环）
            self.model = await asyncio.to_thread(
                SentenceTransformer,
                self.model_name,
                device=self.device
            )

            self._model_loaded = True
            logger.info(f"Embedding model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    async def encode(
        self,
        texts: str | list[str],
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray | list[np.ndarray]:
        """
        文本向量化

        Args:
            texts: 单个文本或文本列表
            normalize: 是否归一化向量
            show_progress: 是否显示进度条

        Returns:
            向量或向量列表
        """
        # 确保模型已加载
        if not self._model_loaded:
            await self.initialize()

        # 处理单个文本
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        try:
            # 检查缓存
            if self.cache_enabled:
                cached_embeddings = []
                uncached_texts = []
                uncached_indices = []

                for i, text in enumerate(texts):
                    cache_key = self._get_cache_key(text)
                    if cache_key in self.cache:
                        cached_embeddings.append((i, self.cache[cache_key]))
                        self.cache_hits += 1
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(i)
                        self.cache_misses += 1

                # 如果全部命中缓存
                if not uncached_texts:
                    logger.debug(f"All {len(texts)} texts found in cache")
                    embeddings = [emb for _, emb in sorted(cached_embeddings)]
                    return embeddings[0] if is_single else embeddings

                # 编码未缓存的文本
                if uncached_texts:
                    logger.debug(
                        f"Encoding {len(uncached_texts)}/{len(texts)} texts "
                        f"(cache hit rate: {self.cache_hits/(self.cache_hits+self.cache_misses):.2%})"
                    )

                    new_embeddings = await asyncio.to_thread(
                        self.model.encode,
                        uncached_texts,
                        normalize_embeddings=normalize,
                        show_progress_bar=show_progress,
                        batch_size=self.batch_size
                    )

                    # 更新缓存
                    for text, embedding in zip(uncached_texts, new_embeddings, strict=False):
                        cache_key = self._get_cache_key(text)
                        self.cache[cache_key] = embedding

                    # 合并结果
                    all_embeddings = [None] * len(texts)

                    for i, emb in cached_embeddings:
                        all_embeddings[i] = emb

                    for i, idx in enumerate(uncached_indices):
                        all_embeddings[idx] = new_embeddings[i]

                    return all_embeddings[0] if is_single else all_embeddings

            else:
                # 不使用缓存，直接编码
                embeddings = await asyncio.to_thread(
                    self.model.encode,
                    texts,
                    normalize_embeddings=normalize,
                    show_progress_bar=show_progress,
                    batch_size=self.batch_size
                )

                return embeddings[0] if is_single else embeddings

        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise

    async def compute_similarity(
        self,
        text1: str,
        text2: str,
        similarity_metric: str = "cosine"
    ) -> float:
        """
        计算两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2
            similarity_metric: 相似度度量 (cosine/dot/euclidean)

        Returns:
            相似度分数
        """
        try:
            # 编码文本
            embeddings = await self.encode([text1, text2])
            emb1, emb2 = embeddings[0], embeddings[1]

            # 计算相似度
            if similarity_metric == "cosine" or similarity_metric == "dot":
                similarity = float(np.dot(emb1, emb2))
            elif similarity_metric == "euclidean":
                distance = np.linalg.norm(emb1 - emb2)
                similarity = 1.0 / (1.0 + distance)
            else:
                raise ValueError(f"Unknown similarity metric: {similarity_metric}")

            return similarity

        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    async def compute_similarities(
        self,
        query_text: str,
        corpus_texts: list[str],
        top_k: int | None = None
    ) -> list[tuple]:
        """
        计算查询文本与语料库的相似度

        Args:
            query_text: 查询文本
            corpus_texts: 语料库文本列表
            top_k: 返回top k个最相似的结果

        Returns:
            [(index, similarity_score), ...] 按相似度降序排列
        """
        try:
            # 编码所有文本
            all_texts = [query_text] + corpus_texts
            embeddings = await self.encode(all_texts)

            query_emb = embeddings[0]
            corpus_embs = np.array(embeddings[1:])

            # 计算余弦相似度
            similarities = np.dot(corpus_embs, query_emb)

            # 创建 (index, score) 对
            results = [(i, float(sim)) for i, sim in enumerate(similarities)]

            # 按相似度降序排序
            results.sort(key=lambda x: x[1], reverse=True)

            # 返回top k
            if top_k:
                results = results[:top_k]

            return results

        except Exception as e:
            logger.error(f"Failed to compute similarities: {e}")
            return []

    async def batch_encode(
        self,
        text_batches: list[list[str]],
        normalize: bool = True
    ) -> list[list[np.ndarray]]:
        """
        批量编码（适用于大规模文本）

        Args:
            text_batches: 文本批次列表
            normalize: 是否归一化

        Returns:
            向量批次列表
        """
        results = []

        for i, batch in enumerate(text_batches):
            logger.info(f"Processing batch {i+1}/{len(text_batches)}")
            embeddings = await self.encode(batch, normalize=normalize)
            results.append(embeddings)

        return results

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0

        return {
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate
        }

    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        return 0

    async def health_check(self) -> dict:
        """健康检查"""
        try:
            if not self._model_loaded:
                await self.initialize()

            # 测试编码
            test_text = "测试文本"
            start_time = time.time()
            await self.encode(test_text)
            elapsed = time.time() - start_time

            return {
                "healthy": True,
                "model_name": self.model_name,
                "model_loaded": self._model_loaded,
                "device": self.device,
                "embedding_dim": self.get_embedding_dim(),
                "test_latency_ms": int(elapsed * 1000),
                "cache_stats": self.get_cache_stats()
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e)
            }


# 全局单例
_embedding_service_instance: EmbeddingService | None = None


async def get_embedding_service(
    model_name: str = None,
    device: str = None
) -> EmbeddingService:
    """获取Embedding服务单例"""
    global _embedding_service_instance

    if _embedding_service_instance is None:
        model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
        device = device or os.getenv("EMBEDDING_DEVICE", "cpu")

        _embedding_service_instance = EmbeddingService(
            model_name=model_name,
            device=device
        )

        # 初始化模型
        await _embedding_service_instance.initialize()

    return _embedding_service_instance
