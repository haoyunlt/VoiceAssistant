"""
带缓存的 Embedder 包装器
自动集成两级向量缓存
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CachedEmbedder:
    """带缓存的 Embedder 包装器"""

    def __init__(
        self,
        embedder,
        vector_cache,
        model_name: str,
    ):
        """
        初始化带缓存的 Embedder

        Args:
            embedder: 原始 Embedder 实例
            vector_cache: VectorCache 实例
            model_name: 模型名称
        """
        self.embedder = embedder
        self.vector_cache = vector_cache
        self.model_name = model_name

        logger.info(f"CachedEmbedder initialized for model: {model_name}")

    async def embed(self, text: str) -> list[float]:
        """
        单个文本向量化（带缓存）

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        return await self.vector_cache.get_or_compute(
            text=text,
            model=self.model_name,
            compute_fn=lambda: self.embedder.embed(text),
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量文本向量化（带缓存）

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        return await self.vector_cache.get_batch_or_compute(
            texts=texts,
            model=self.model_name,
            compute_fn=lambda uncached_texts: self.embedder.embed_batch(uncached_texts),
        )

    async def embed_query(self, query: str) -> list[float]:
        """
        查询向量化（带缓存）

        Args:
            query: 查询文本

        Returns:
            向量列表
        """
        # 对于查询，可能需要特殊处理（如添加前缀）
        # 这里先使用相同的缓存逻辑
        return await self.vector_cache.get_or_compute(
            text=f"query:{query}",  # 添加前缀以区分文档和查询
            model=self.model_name,
            compute_fn=lambda: self.embedder.embed_query(query),
        )

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.embedder.get_dimension()

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        return self.vector_cache.get_stats()

    async def warmup_cache(
        self,
        texts: list[str],
        batch_size: int = 32,
    ):
        """
        缓存预热

        Args:
            texts: 文本列表
            batch_size: 批量大小
        """
        await self.vector_cache.warmup(
            texts=texts,
            model=self.model_name,
            compute_fn=lambda batch_texts: self.embedder.embed_batch(batch_texts),
            batch_size=batch_size,
        )

    async def invalidate_cache(self, text: str):
        """
        使缓存失效

        Args:
            text: 文本内容
        """
        await self.vector_cache.invalidate(text, self.model_name)

    async def clear_cache(self):
        """清空缓存"""
        await self.vector_cache.clear(self.model_name)


class MultiModelCachedEmbedder:
    """多模型带缓存的 Embedder"""

    def __init__(
        self,
        embedders: dict[str, Any],
        multi_model_cache,
    ):
        """
        初始化多模型带缓存的 Embedder

        Args:
            embedders: 模型名称 -> Embedder 实例的字典
            multi_model_cache: MultiModelVectorCache 实例
        """
        self.embedders = embedders
        self.multi_model_cache = multi_model_cache

        logger.info(
            f"MultiModelCachedEmbedder initialized with {len(embedders)} models"
        )

    async def embed(
        self,
        text: str,
        model: str = "default",
    ) -> list[float]:
        """
        单个文本向量化（指定模型）

        Args:
            text: 输入文本
            model: 模型名称

        Returns:
            向量列表
        """
        if model not in self.embedders:
            raise ValueError(f"Model {model} not found in embedders")

        embedder = self.embedders[model]

        return await self.multi_model_cache.get_or_compute(
            text=text,
            model=model,
            compute_fn=lambda: embedder.embed(text),
        )

    async def embed_batch(
        self,
        texts: list[str],
        model: str = "default",
    ) -> list[list[float]]:
        """
        批量文本向量化（指定模型）

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            向量列表
        """
        if model not in self.embedders:
            raise ValueError(f"Model {model} not found in embedders")

        embedder = self.embedders[model]

        return await self.multi_model_cache.get_batch_or_compute(
            texts=texts,
            model=model,
            compute_fn=lambda uncached_texts: embedder.embed_batch(uncached_texts),
        )

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有模型的缓存统计"""
        return self.multi_model_cache.get_all_stats()

    async def clear_all_caches(self):
        """清空所有缓存"""
        await self.multi_model_cache.clear_all()


class CacheConfig:
    """缓存配置"""

    def __init__(
        self,
        enable_l1: bool = True,
        enable_l2: bool = True,
        l1_max_size: int = 10000,
        l2_ttl: int = 604800,  # 7天
        l1_max_size_per_model: int = 10000,
    ):
        """
        初始化缓存配置

        Args:
            enable_l1: 是否启用 L1 缓存
            enable_l2: 是否启用 L2 缓存
            l1_max_size: L1 缓存最大条目数
            l2_ttl: L2 缓存 TTL（秒）
            l1_max_size_per_model: 每个模型的 L1 缓存大小
        """
        self.enable_l1 = enable_l1
        self.enable_l2 = enable_l2
        self.l1_max_size = l1_max_size
        self.l2_ttl = l2_ttl
        self.l1_max_size_per_model = l1_max_size_per_model

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """从环境变量加载配置"""
        import os

        return cls(
            enable_l1=os.getenv("CACHE_ENABLE_L1", "true").lower() == "true",
            enable_l2=os.getenv("CACHE_ENABLE_L2", "true").lower() == "true",
            l1_max_size=int(os.getenv("CACHE_L1_MAX_SIZE", "10000")),
            l2_ttl=int(os.getenv("CACHE_L2_TTL", "604800")),
            l1_max_size_per_model=int(
                os.getenv("CACHE_L1_MAX_SIZE_PER_MODEL", "10000")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "enable_l1": self.enable_l1,
            "enable_l2": self.enable_l2,
            "l1_max_size": self.l1_max_size,
            "l2_ttl": self.l2_ttl,
            "l1_max_size_per_model": self.l1_max_size_per_model,
        }
