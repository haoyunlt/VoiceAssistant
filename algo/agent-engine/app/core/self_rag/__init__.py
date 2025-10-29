"""
Self-RAG 核心模块

包含检索质量评估、自适应检索策略、幻觉检测等功能。
"""

from app.core.self_rag.adaptive_retriever import AdaptiveRetriever
from app.core.self_rag.critique import RetrievalCritic
from app.core.self_rag.hallucination_detector import HallucinationDetector

__all__ = [
    "RetrievalCritic",
    "AdaptiveRetriever",
    "HallucinationDetector",
]
