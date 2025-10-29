"""
重排序服务 - LLM-based Reranking
支持多种重排序策略：Cross-Encoder, LLM, Cohere Rerank API
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class RerankerBackend(str, Enum):
    """重排序后端类型"""
    CROSS_ENCODER = "cross_encoder"  # Sentence-Transformers Cross-Encoder
    LLM = "llm"  # 使用 LLM 进行重排序
    COHERE = "cohere"  # Cohere Rerank API
    SIMPLE = "simple"  # 简单的规则重排序（后备）


class RerankerService:
    """重排序服务"""

    def __init__(
        self,
        backend: str = "llm",
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        """
        初始化重排序服务

        Args:
            backend: 重排序后端（cross_encoder/llm/cohere/simple）
            model_name: 模型名称
            api_key: API密钥（Cohere需要）
        """
        self.backend = backend
        self.model_name = model_name or self._get_default_model()
        self.api_key = api_key
        self.model = None

        logger.info(
            f"Reranker Service initialized with backend={backend}, model={self.model_name}"
        )

    def _get_default_model(self) -> str:
        """获取默认模型"""
        defaults = {
            RerankerBackend.CROSS_ENCODER: "cross-encoder/ms-marco-MiniLM-L-6-v2",
            RerankerBackend.LLM: "gpt-3.5-turbo",
            RerankerBackend.COHERE: "rerank-english-v2.0",
            RerankerBackend.SIMPLE: "none",
        }
        return defaults.get(self.backend, "none")

    async def initialize(self):
        """初始化重排序模型"""
        try:
            if self.backend == RerankerBackend.CROSS_ENCODER:
                await self._init_cross_encoder()
            elif self.backend == RerankerBackend.LLM:
                await self._init_llm()
            elif self.backend == RerankerBackend.COHERE:
                await self._init_cohere()
            elif self.backend == RerankerBackend.SIMPLE:
                logger.info("Using simple reranker (no model required)")
            else:
                raise ValueError(f"Unsupported reranker backend: {self.backend}")

            logger.info(f"Reranker model loaded successfully: {self.backend}")
        except Exception as e:
            logger.warning(
                f"Failed to load reranker model {self.backend}: {e}, "
                f"falling back to simple reranker"
            )
            self.backend = RerankerBackend.SIMPLE

    async def _init_cross_encoder(self):
        """初始化 Cross-Encoder 模型"""
        try:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(self.model_name)
            logger.info(f"Cross-Encoder model loaded: {self.model_name}")
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

    async def _init_llm(self):
        """初始化 LLM 客户端"""
        # 使用 OpenAI API 或其他 LLM API
        self.model = "llm_client"  # 占位符
        logger.info("LLM-based reranker initialized")

    async def _init_cohere(self):
        """初始化 Cohere Rerank API"""
        try:
            import cohere

            if not self.api_key:
                raise ValueError("Cohere API key is required")

            self.model = cohere.Client(self.api_key)
            logger.info("Cohere Rerank API initialized")
        except ImportError:
            raise ImportError("cohere not installed. Run: pip install cohere")

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 文档列表，每个文档包含 {content, score, ...}
            top_k: 返回前K个结果（None表示全部）

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        try:
            if self.backend == RerankerBackend.CROSS_ENCODER:
                return await self._rerank_cross_encoder(query, documents, top_k)
            elif self.backend == RerankerBackend.LLM:
                return await self._rerank_llm(query, documents, top_k)
            elif self.backend == RerankerBackend.COHERE:
                return await self._rerank_cohere(query, documents, top_k)
            elif self.backend == RerankerBackend.SIMPLE:
                return await self._rerank_simple(query, documents, top_k)
            else:
                return documents[:top_k] if top_k else documents

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            # 失败时返回原始顺序
            return documents[:top_k] if top_k else documents

    async def _rerank_cross_encoder(
        self, query: str, documents: list[dict], top_k: int | None
    ) -> list[dict]:
        """使用 Cross-Encoder 重排序"""
        # 准备输入对
        pairs = [(query, doc.get("content", doc.get("text", ""))) for doc in documents]

        # 批量计算相关性分数
        scores = self.model.predict(pairs)

        # 合并分数并排序
        reranked = []
        for doc, score in zip(documents, scores, strict=False):
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = float(score)
            reranked.append(doc_copy)

        # 按重排序分数排序
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_k] if top_k else reranked

    async def _rerank_llm(
        self, query: str, documents: list[dict], top_k: int | None
    ) -> list[dict]:
        """使用 LLM 重排序"""
        # 构建 prompt
        docs_text = []
        for i, doc in enumerate(documents):
            content = doc.get("content", doc.get("text", ""))
            docs_text.append(f"[{i}] {content[:200]}...")  # 限制长度

        prompt = f"""Given a query and a list of documents, rank the documents by their relevance to the query.

Query: {query}

Documents:
{chr(10).join(docs_text)}

Please return the document indices in order of relevance (most relevant first), as a comma-separated list of integers.
Example: 2,0,4,1,3

Ranked indices:"""

        try:
            import os

            import httpx

            # 调用 LLM API（这里使用 OpenAI 作为示例）
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 100,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    ranked_text = data["choices"][0]["message"]["content"].strip()

                    # 解析排序结果
                    try:
                        ranked_indices = [
                            int(idx.strip()) for idx in ranked_text.split(",")
                        ]

                        # 按照排序结果重排
                        reranked = []
                        for rank, idx in enumerate(ranked_indices):
                            if 0 <= idx < len(documents):
                                doc_copy = documents[idx].copy()
                                doc_copy["rerank_score"] = 1.0 - (rank / len(ranked_indices))
                                reranked.append(doc_copy)

                        # 添加未被排序的文档
                        ranked_set = set(ranked_indices)
                        for idx, doc in enumerate(documents):
                            if idx not in ranked_set:
                                doc_copy = doc.copy()
                                doc_copy["rerank_score"] = 0.0
                                reranked.append(doc_copy)

                        return reranked[:top_k] if top_k else reranked

                    except ValueError as e:
                        logger.warning(f"Failed to parse LLM ranking result: {e}")
                        return documents[:top_k] if top_k else documents

                else:
                    logger.error(f"LLM API failed: {response.status_code}")
                    return documents[:top_k] if top_k else documents

        except Exception as e:
            logger.error(f"LLM reranking failed: {e}")
            return documents[:top_k] if top_k else documents

    async def _rerank_cohere(
        self, query: str, documents: list[dict], top_k: int | None
    ) -> list[dict]:
        """使用 Cohere Rerank API 重排序"""
        try:
            # 准备文档文本
            texts = [doc.get("content", doc.get("text", "")) for doc in documents]

            # 调用 Cohere Rerank API
            results = self.model.rerank(
                query=query,
                documents=texts,
                top_n=top_k or len(texts),
                model=self.model_name,
            )

            # 重排序
            reranked = []
            for result in results:
                doc_copy = documents[result.index].copy()
                doc_copy["rerank_score"] = result.relevance_score
                reranked.append(doc_copy)

            return reranked

        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")
            return documents[:top_k] if top_k else documents

    async def _rerank_simple(
        self, query: str, documents: list[dict], top_k: int | None
    ) -> list[dict]:
        """简单重排序（基于规则）"""
        # 基于简单规则：
        # 1. 关键词匹配
        # 2. 长度惩罚
        # 3. 原始分数

        query_lower = query.lower()
        query_words = set(query_lower.split())

        reranked = []
        for doc in documents:
            content = doc.get("content", doc.get("text", "")).lower()
            original_score = doc.get("score", 0.0)

            # 关键词匹配分数
            content_words = set(content.split())
            keyword_score = len(query_words & content_words) / max(len(query_words), 1)

            # 长度惩罚（避免过长或过短）
            length_penalty = 1.0
            if len(content) < 50:
                length_penalty = 0.5
            elif len(content) > 2000:
                length_penalty = 0.8

            # 综合分数
            rerank_score = (
                0.5 * original_score + 0.3 * keyword_score + 0.2 * length_penalty
            )

            doc_copy = doc.copy()
            doc_copy["rerank_score"] = rerank_score
            reranked.append(doc_copy)

        # 排序
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_k] if top_k else reranked


# 全局重排序服务实例
_reranker_service_instance: RerankerService | None = None


async def get_reranker_service(
    backend: str = "simple", model_name: str | None = None, api_key: str | None = None
) -> RerankerService:
    """
    获取重排序服务单例

    Args:
        backend: 重排序后端
        model_name: 模型名称
        api_key: API密钥

    Returns:
        重排序服务实例
    """
    global _reranker_service_instance

    if _reranker_service_instance is None:
        _reranker_service_instance = RerankerService(
            backend=backend, model_name=model_name, api_key=api_key
        )
        await _reranker_service_instance.initialize()

    return _reranker_service_instance
