"""
Hybrid Retriever - 混合检索器

结合 BM25 和向量检索，使用 Reciprocal Rank Fusion (RRF) 融合结果
"""

import os
from typing import Any, Dict, List, Optional

import logging
from app.retrieval.bm25_retriever import get_bm25_retriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索器"""

    def __init__(
        self,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        rrf_k: int = 60,
    ):
        """
        初始化混合检索器

        Args:
            bm25_weight: BM25 权重
            vector_weight: 向量检索权重
            rrf_k: RRF 参数 k
        """
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k

        # 获取 BM25 检索器
        self.bm25_retriever = get_bm25_retriever()

        logger.info(
            f"Hybrid retriever initialized: bm25_weight={bm25_weight}, vector_weight={vector_weight}"
        )

    def retrieve(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        top_k: int = 10,
        fusion_method: str = "rrf",  # "rrf" or "weighted_sum"
    ) -> List[Dict[str, Any]]:
        """
        混合检索

        Args:
            query: 查询文本
            vector_results: 向量检索结果（已包含分数）
            top_k: 返回的 top-k 结果
            fusion_method: 融合方法（"rrf" 或 "weighted_sum"）

        Returns:
            混合检索结果
        """
        try:
            # 1. 获取 BM25 结果
            bm25_results = self.bm25_retriever.retrieve(
                query=query, top_k=top_k * 2  # 检索更多结果用于融合
            )

            logger.info(
                f"Retrieved {len(bm25_results)} BM25 results, {len(vector_results)} vector results"
            )

            # 2. 融合结果
            if fusion_method == "rrf":
                fused_results = self._reciprocal_rank_fusion(
                    bm25_results, vector_results
                )
            else:  # weighted_sum
                fused_results = self._weighted_sum_fusion(bm25_results, vector_results)

            # 3. 返回 top-k
            return fused_results[:top_k]

        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}", exc_info=True)
            # 失败时返回向量检索结果
            return vector_results[:top_k]

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF)

        RRF(d) = sum(1 / (k + rank_i(d)))

        Args:
            bm25_results: BM25 结果
            vector_results: 向量结果

        Returns:
            融合后的结果
        """
        # 创建文档 ID 到文档的映射
        doc_map = {}

        # 创建文档 ID 到 RRF 分数的映射
        rrf_scores = {}

        # 处理 BM25 结果
        for rank, doc in enumerate(bm25_results, start=1):
            doc_id = doc.get("id") or doc.get("doc_id") or str(hash(doc.get("text", "")))
            doc_map[doc_id] = doc
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.rrf_k + rank)

        # 处理向量结果
        for rank, doc in enumerate(vector_results, start=1):
            doc_id = doc.get("id") or doc.get("doc_id") or str(hash(doc.get("text", "")))
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.rrf_k + rank)

        # 创建融合结果
        fused_results = []
        for doc_id, rrf_score in rrf_scores.items():
            doc = doc_map[doc_id].copy()
            doc["rrf_score"] = rrf_score
            doc["fusion_method"] = "rrf"
            fused_results.append(doc)

        # 按 RRF 分数排序
        fused_results = sorted(
            fused_results, key=lambda x: x["rrf_score"], reverse=True
        )

        return fused_results

    def _weighted_sum_fusion(
        self,
        bm25_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        加权求和融合

        weighted_score = bm25_weight * norm(bm25_score) + vector_weight * norm(vector_score)

        Args:
            bm25_results: BM25 结果
            vector_results: 向量结果

        Returns:
            融合后的结果
        """
        # 归一化分数
        def normalize_scores(results, score_key):
            scores = [doc.get(score_key, 0) for doc in results]
            if not scores or max(scores) == min(scores):
                return results
            min_score, max_score = min(scores), max(scores)
            for doc in results:
                score = doc.get(score_key, 0)
                doc[f"norm_{score_key}"] = (score - min_score) / (max_score - min_score)
            return results

        # 归一化 BM25 分数
        bm25_results = normalize_scores(bm25_results, "bm25_score")

        # 归一化向量分数（假设键名为 'score' 或 'distance'）
        vector_score_key = "score" if any("score" in doc for doc in vector_results) else "distance"
        vector_results = normalize_scores(vector_results, vector_score_key)

        # 创建文档 ID 到文档的映射
        doc_map = {}
        weighted_scores = {}

        # 处理 BM25 结果
        for doc in bm25_results:
            doc_id = doc.get("id") or doc.get("doc_id") or str(hash(doc.get("text", "")))
            doc_map[doc_id] = doc
            bm25_norm_score = doc.get("norm_bm25_score", 0)
            weighted_scores[doc_id] = self.bm25_weight * bm25_norm_score

        # 处理向量结果
        for doc in vector_results:
            doc_id = doc.get("id") or doc.get("doc_id") or str(hash(doc.get("text", "")))
            if doc_id not in doc_map:
                doc_map[doc_id] = doc
            vector_norm_score = doc.get(f"norm_{vector_score_key}", 0)
            weighted_scores[doc_id] = (
                weighted_scores.get(doc_id, 0) + self.vector_weight * vector_norm_score
            )

        # 创建融合结果
        fused_results = []
        for doc_id, weighted_score in weighted_scores.items():
            doc = doc_map[doc_id].copy()
            doc["weighted_score"] = weighted_score
            doc["fusion_method"] = "weighted_sum"
            fused_results.append(doc)

        # 按加权分数排序
        fused_results = sorted(
            fused_results, key=lambda x: x["weighted_score"], reverse=True
        )

        return fused_results

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        bm25_health = self.bm25_retriever.health_check()

        return {
            "healthy": bm25_health["healthy"],
            "bm25_healthy": bm25_health["healthy"],
            "bm25_weight": self.bm25_weight,
            "vector_weight": self.vector_weight,
            "rrf_k": self.rrf_k,
        }


# 全局实例
_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    """
    获取混合检索器实例（单例）

    Returns:
        HybridRetriever 实例
    """
    global _hybrid_retriever

    if _hybrid_retriever is None:
        bm25_weight = float(os.getenv("HYBRID_BM25_WEIGHT", "0.5"))
        vector_weight = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5"))
        rrf_k = int(os.getenv("HYBRID_RRF_K", "60"))

        _hybrid_retriever = HybridRetriever(
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            rrf_k=rrf_k,
        )

    return _hybrid_retriever
