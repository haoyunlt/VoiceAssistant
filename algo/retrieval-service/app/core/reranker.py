"""重排序器 - Cross-Encoder"""

import logging
from typing import Dict, List

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-Encoder 重排序器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        """
        初始化重排序器

        Args:
            model_name: Cross-Encoder 模型名称
        """
        self.model_name = model_name
        self.model = None
        logger.info(f"Reranker created with model: {model_name}")

    async def initialize(self):
        """初始化模型"""
        logger.info(f"Loading reranker model: {self.model_name}...")

        # 加载 Cross-Encoder 模型
        self.model = CrossEncoder(self.model_name)

        logger.info("Reranker model loaded successfully")

    async def rerank(
        self, query: str, documents: List[Dict], top_k: int = 10
    ) -> List[Dict]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回结果数

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        # 提取文档内容
        doc_contents = [doc.get("content", "") for doc in documents]

        # 构建查询-文档对
        query_doc_pairs = [[query, doc] for doc in doc_contents]

        # 计算相关性分数
        scores = self.model.predict(query_doc_pairs)

        # 将分数添加到文档
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        # 按分数排序
        reranked = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)

        # 取 Top K
        top_results = reranked[:top_k]

        logger.info(f"Reranked {len(documents)} → {len(top_results)} documents")

        return top_results


class LLMReranker:
    """基于 LLM 的重排序器（可选）"""

    def __init__(self):
        """初始化 LLM 重排序器"""
        self.llm_client = None
        logger.info("LLM reranker created")

    async def initialize(self):
        """初始化 LLM 客户端"""
        # TODO: 初始化 LLM 客户端
        pass

    async def rerank(
        self, query: str, documents: List[Dict], top_k: int = 10
    ) -> List[Dict]:
        """
        使用 LLM 重排序文档

        通过 LLM 评估查询与文档的相关性
        """
        # TODO: 实现 LLM 重排序
        return documents[:top_k]
