"""
Hybrid search service (Vector + BM25 + RRF)
"""

from typing import Dict, List

from app.core.config import settings
import logging
from app.models.retrieval import RetrievalDocument

logger = logging.getLogger(__name__)


class HybridService:
    """混合检索服务（RRF 融合）"""

    def __init__(self, rrf_k: int = 60):
        """
        Args:
            rrf_k: RRF 参数，用于平衡不同来源的分数
        """
        self.rrf_k = rrf_k

    async def fuse_results(
        self,
        vector_docs: List[RetrievalDocument],
        bm25_docs: List[RetrievalDocument],
        top_k: int,
    ) -> List[RetrievalDocument]:
        """
        使用 RRF (Reciprocal Rank Fusion) 融合向量和 BM25 检索结果

        RRF Score = sum(1 / (k + rank_i))

        Args:
            vector_docs: 向量检索结果
            bm25_docs: BM25 检索结果
            top_k: 返回的文档数量

        Returns:
            融合后的文档列表
        """
        logger.info(f"Fusing results: vector={len(vector_docs)}, bm25={len(bm25_docs)}")

        # 计算 RRF 分数
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, RetrievalDocument] = {}

        # 向量检索结果
        for rank, doc in enumerate(vector_docs, start=1):
            key = doc.chunk_id
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))
            if key not in doc_map:
                doc_map[key] = doc

        # BM25 检索结果
        for rank, doc in enumerate(bm25_docs, start=1):
            key = doc.chunk_id
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (self.rrf_k + rank))
            if key not in doc_map:
                doc_map[key] = doc

        # 按 RRF 分数排序
        sorted_keys = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 构建融合结果
        fused_docs = []
        for key, score in sorted_keys[:top_k]:
            doc = doc_map[key]
            # 更新分数和来源
            doc.score = score
            doc.source = "hybrid"
            fused_docs.append(doc)

        logger.info(f"Fusion completed: {len(fused_docs)} documents")
        return fused_docs
