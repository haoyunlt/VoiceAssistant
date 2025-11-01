"""
Reranking service (Cross-Encoder or LLM)
"""

import asyncio
import logging

import httpx
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.models.retrieval import RetrievalDocument

logger = logging.getLogger(__name__)


class RerankService:
    """重排序服务"""

    def __init__(self):
        self.model_type = settings.RERANK_MODEL
        self.cross_encoder: CrossEncoder | None = None

        if self.model_type == "cross-encoder":
            self._load_cross_encoder()

    def _load_cross_encoder(self):
        """加载 Cross-Encoder 模型"""
        try:
            self.cross_encoder = CrossEncoder(settings.CROSS_ENCODER_MODEL)
            logger.info(f"Loaded Cross-Encoder model: {settings.CROSS_ENCODER_MODEL}")
        except Exception as e:
            logger.error(f"Failed to load Cross-Encoder model: {e}")

    async def rerank(
        self, query: str, documents: list[RetrievalDocument], top_k: int
    ) -> list[RetrievalDocument]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 待重排序的文档列表
            top_k: 返回的文档数量

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        if self.model_type == "cross-encoder":
            return await self._rerank_with_cross_encoder(query, documents, top_k)
        elif self.model_type == "llm":
            return await self._rerank_with_llm(query, documents, top_k)
        else:
            logger.warning(
                f"Unknown rerank model type: {self.model_type}, returning original order"
            )
            return documents[:top_k]

    async def _rerank_with_cross_encoder(
        self, query: str, documents: list[RetrievalDocument], top_k: int
    ) -> list[RetrievalDocument]:
        """使用 Cross-Encoder 重排序"""
        if not self.cross_encoder:
            logger.warning("Cross-Encoder not loaded, returning original order")
            return documents[:top_k]

        try:
            # 准备输入对
            pairs = [[query, doc.content] for doc in documents]

            # 预测分数（在线程池中运行以避免阻塞）
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(None, self.cross_encoder.predict, pairs)

            # 更新文档分数并排序
            for doc, score in zip(documents, scores, strict=False):
                doc.score = float(score)

            reranked_docs = sorted(documents, key=lambda x: x.score, reverse=True)[:top_k]

            logger.info(f"Cross-Encoder reranking completed: {len(reranked_docs)} documents")
            return reranked_docs

        except Exception as e:
            logger.error(f"Cross-Encoder reranking failed: {e}", exc_info=True)
            return documents[:top_k]

    async def _rerank_with_llm(
        self, query: str, documents: list[RetrievalDocument], top_k: int
    ) -> list[RetrievalDocument]:
        """使用 LLM 重排序"""
        try:
            # 构建重排序提示
            prompt = self._build_rerank_prompt(query, documents)

            # 调用 LLM
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.LLM_RERANK_ENDPOINT}/api/v1/chat/completions",
                    json={
                        "model": settings.LLM_RERANK_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

            # 解析 LLM 响应并重排序
            reranked_docs = self._parse_llm_rerank_response(result, documents)[:top_k]

            logger.info(f"LLM reranking completed: {len(reranked_docs)} documents")
            return reranked_docs

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}", exc_info=True)
            return documents[:top_k]

    def _build_rerank_prompt(self, query: str, documents: list[RetrievalDocument]) -> str:
        """构建重排序提示"""
        docs_text = "\n\n".join(
            [f"[{i}] {doc.content[:200]}..." for i, doc in enumerate(documents)]
        )

        prompt = f"""Given the following query and documents, rank the documents by relevance to the query.
Return a comma-separated list of document indices in descending order of relevance.

Query: {query}

Documents:
{docs_text}

Ranking (indices only, e.g., "2,0,1,3"):"""

        return prompt

    def _parse_llm_rerank_response(
        self, llm_response: dict, documents: list[RetrievalDocument]
    ) -> list[RetrievalDocument]:
        """解析 LLM 重排序响应"""
        try:
            # 提取排序结果
            content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
            indices = [int(idx.strip()) for idx in content.split(",") if idx.strip().isdigit()]

            # 按排序结果重排文档
            reranked_docs = []
            for idx in indices:
                if 0 <= idx < len(documents):
                    reranked_docs.append(documents[idx])

            # 添加未排序的文档（按原顺序）
            ranked_indices = set(indices)
            for i, doc in enumerate(documents):
                if i not in ranked_indices:
                    reranked_docs.append(doc)

            return reranked_docs

        except Exception as e:
            logger.error(f"Failed to parse LLM rerank response: {e}")
            return documents
