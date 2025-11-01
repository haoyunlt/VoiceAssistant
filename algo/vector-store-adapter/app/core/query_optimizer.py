"""Query optimizer for vector search"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Optimize vector search parameters based on query characteristics

    Features:
    - Auto-adjust HNSW ef parameter based on top_k
    - IVFFlat lists recommendation
    - Search params optimization
    """

    @staticmethod
    def optimize_search_params(
        backend: str,
        top_k: int,
        collection_size: int | None = None,
        search_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Optimize search parameters

        Args:
            backend: Backend type (milvus/pgvector)
            top_k: Number of results
            collection_size: Collection size (if known)
            search_params: User-provided search params (overrides optimization)

        Returns:
            Optimized search parameters
        """
        # If user provides params, use them
        if search_params:
            return search_params

        if backend == "milvus":
            return QueryOptimizer._optimize_milvus_params(top_k, collection_size)
        elif backend == "pgvector":
            return QueryOptimizer._optimize_pgvector_params(top_k, collection_size)
        else:
            return {}

    @staticmethod
    def _optimize_milvus_params(
        top_k: int,
        _collection_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Optimize Milvus HNSW parameters

        HNSW ef parameter controls recall vs latency trade-off:
        - Higher ef = better recall, higher latency
        - Lower ef = faster search, lower recall

        Recommended: ef >= top_k * 2 for good recall
        """
        # Auto-adjust ef based on top_k
        if top_k <= 10:
            ef = 64
        elif top_k <= 50:
            ef = 128
        elif top_k <= 100:
            ef = 256
        else:
            ef = min(512, top_k * 3)

        params = {
            "metric_type": "IP",  # Inner Product (for cosine similarity)
            "params": {
                "ef": ef,
            },
        }

        logger.debug(f"Optimized Milvus params for top_k={top_k}: {params}")
        return params

    @staticmethod
    def _optimize_pgvector_params(
        top_k: int,
        collection_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Optimize pgvector parameters

        pgvector uses IVFFlat or HNSW index:
        - IVFFlat: faster indexing, requires manual list selection
        - HNSW: slower indexing, better search performance
        """
        # For IVFFlat, recommend probes based on collection size
        if collection_size:
            # Rule of thumb: lists = sqrt(rows)
            # probes = lists / 10 for good recall
            lists = max(10, int(collection_size**0.5))
            probes = max(1, lists // 10)
        else:
            probes = 10  # Default

        params = {
            "probes": probes,  # For IVFFlat
        }

        logger.debug(
            f"Optimized pgvector params for top_k={top_k}, size={collection_size}: {params}"
        )
        return params

    @staticmethod
    def recommend_index_params(
        backend: str,
        dimension: int,
        collection_size: int,
    ) -> dict[str, Any]:
        """
        Recommend index parameters for collection creation

        Args:
            backend: Backend type
            dimension: Vector dimension
            collection_size: Expected collection size

        Returns:
            Recommended index parameters
        """
        if backend == "milvus":
            return QueryOptimizer._recommend_milvus_index(dimension, collection_size)
        elif backend == "pgvector":
            return QueryOptimizer._recommend_pgvector_index(dimension, collection_size)
        else:
            return {}

    @staticmethod
    def _recommend_milvus_index(
        _dimension: int,
        collection_size: int,
    ) -> dict[str, Any]:
        """
        Recommend Milvus index parameters

        HNSW parameters:
        - M: number of connections (8-64)
        - efConstruction: construction time/quality trade-off (64-512)

        Guidelines:
        - Small collections (<10K): M=16, efConstruction=200
        - Medium collections (10K-1M): M=32, efConstruction=256
        - Large collections (>1M): M=64, efConstruction=512
        """
        if collection_size < 10_000:
            m = 16
            ef_construction = 200
        elif collection_size < 1_000_000:
            m = 32
            ef_construction = 256
        else:
            m = 64
            ef_construction = 512

        return {
            "index_type": "HNSW",
            "metric_type": "IP",
            "params": {
                "M": m,
                "efConstruction": ef_construction,
            },
        }

    @staticmethod
    def _recommend_pgvector_index(
        _dimension: int,
        collection_size: int,
    ) -> dict[str, Any]:
        """
        Recommend pgvector index parameters

        IVFFlat lists:
        - Rule of thumb: lists = sqrt(rows)
        - Too few lists = slow search
        - Too many lists = slow indexing + memory overhead

        Guidelines:
        - <10K rows: lists=50
        - 10K-100K rows: lists=100
        - 100K-1M rows: lists=500
        - >1M rows: lists=1000
        """
        if collection_size < 10_000:
            lists = 50
        elif collection_size < 100_000:
            lists = 100
        elif collection_size < 1_000_000:
            lists = 500
        else:
            lists = 1000

        return {
            "index_type": "ivfflat",
            "lists": lists,
            "probes": max(1, lists // 10),  # For query time
        }


# Singleton instance
query_optimizer = QueryOptimizer()
