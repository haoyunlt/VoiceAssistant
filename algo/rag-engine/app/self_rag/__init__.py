"""
Self-RAG 模块

提供自我纠错和幻觉检测功能
"""

from app.self_rag.hallucination_detector import HallucinationDetector
from app.self_rag.self_rag_service import SelfRAGService

__all__ = [
    "HallucinationDetector",
    "SelfRAGService",
]
