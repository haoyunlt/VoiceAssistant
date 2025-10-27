"""
Re-ranker - 检索结果重排序器

使用交叉编码器（Cross-Encoder）对检索结果进行重新排序，
提升检索精度
"""

from typing import List, Dict, Any, Optional
import os

try:
    from sentence_transformers import CrossEncoder
    CROSS_ENCODER_AVAILABLE = True
except ImportError:
    CROSS_ENCODER_AVAILABLE = False
    CrossEncoder = None

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class ReRanker:
    """检索结果重排序器"""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k: int = 10,
        device: str = "cpu",
    ):
        """
        初始化 Re-ranker

        Args:
            model_name: 交叉编码器模型名称
            top_k: 返回的 top-k 结果数量
            device: 设备（cpu 或 cuda）
        """
        if not CROSS_ENCODER_AVAILABLE:
            logger.warning(
                "sentence-transformers not installed. Re-ranking disabled. "
                "Install with: pip install sentence-transformers"
            )
            self.model = None
        else:
            try:
                self.model = CrossEncoder(model_name, max_length=512, device=device)
                logger.info(f"Re-ranker initialized: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load re-ranker model: {e}")
                self.model = None

        self.top_k = top_k

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], score_key: str = "score"
    ) -> List[Dict[str, Any]]:
        """
        重新排序文档

        Args:
            query: 查询文本
            documents: 文档列表，每个文档包含 'text' 和可选的 'score'
            score_key: 原始分数的键名

        Returns:
            重新排序后的文档列表
        """
        if not self.model:
            # 如果模型未加载，返回原始结果
            logger.warning("Re-ranker not available, returning original results")
            return documents[: self.top_k]

        if not documents:
            return []

        try:
            # 准备输入对：[(query, doc_text), ...]
            pairs = []
            for doc in documents:
                doc_text = doc.get("text", "") or doc.get("content", "")
                pairs.append([query, doc_text])

            # 计算交叉编码分数
            cross_scores = self.model.predict(pairs)

            # 为每个文档添加重排序分数
            for i, doc in enumerate(documents):
                doc["rerank_score"] = float(cross_scores[i])
                # 保留原始分数
                if score_key in doc and "original_score" not in doc:
                    doc["original_score"] = doc[score_key]

            # 按重排序分数排序
            reranked_docs = sorted(
                documents, key=lambda x: x["rerank_score"], reverse=True
            )

            # 返回 top-k
            return reranked_docs[: self.top_k]

        except Exception as e:
            logger.error(f"Re-ranking failed: {e}", exc_info=True)
            # 失败时返回原始结果
            return documents[: self.top_k]

    def rerank_with_fusion(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        original_weight: float = 0.3,
        rerank_weight: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        使用分数融合进行重排序

        结合原始检索分数和重排序分数

        Args:
            query: 查询文本
            documents: 文档列表
            original_weight: 原始分数权重
            rerank_weight: 重排序分数权重

        Returns:
            重新排序后的文档列表
        """
        if not self.model or not documents:
            return documents[: self.top_k]

        try:
            # 首先进行重排序
            reranked_docs = self.rerank(query, documents)

            # 归一化分数
            def normalize_scores(docs, score_key):
                scores = [doc.get(score_key, 0) for doc in docs]
                if not scores or max(scores) == min(scores):
                    return docs
                min_score, max_score = min(scores), max(scores)
                for doc in docs:
                    score = doc.get(score_key, 0)
                    doc[f"norm_{score_key}"] = (score - min_score) / (
                        max_score - min_score
                    )
                return docs

            # 归一化原始分数和重排序分数
            reranked_docs = normalize_scores(reranked_docs, "original_score")
            reranked_docs = normalize_scores(reranked_docs, "rerank_score")

            # 计算融合分数
            for doc in reranked_docs:
                orig_score = doc.get("norm_original_score", 0.5)
                rerank_score = doc.get("norm_rerank_score", 0.5)
                doc["fusion_score"] = (
                    original_weight * orig_score + rerank_weight * rerank_score
                )

            # 按融合分数排序
            reranked_docs = sorted(
                reranked_docs, key=lambda x: x["fusion_score"], reverse=True
            )

            return reranked_docs[: self.top_k]

        except Exception as e:
            logger.error(f"Re-ranking with fusion failed: {e}")
            return documents[: self.top_k]

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        if not CROSS_ENCODER_AVAILABLE:
            return {
                "healthy": False,
                "error": "sentence-transformers not installed",
            }

        if not self.model:
            return {
                "healthy": False,
                "error": "Re-ranker model not loaded",
            }

        return {
            "healthy": True,
            "model_loaded": True,
            "top_k": self.top_k,
        }


# 全局实例
_reranker: Optional[ReRanker] = None


def get_reranker() -> ReRanker:
    """
    获取 Re-ranker 实例（单例）

    Returns:
        ReRanker 实例
    """
    global _reranker

    if _reranker is None:
        model_name = os.getenv(
            "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        top_k = int(os.getenv("RERANK_TOP_K", "10"))
        device = os.getenv("RERANK_DEVICE", "cpu")

        _reranker = ReRanker(model_name=model_name, top_k=top_k, device=device)

    return _reranker
