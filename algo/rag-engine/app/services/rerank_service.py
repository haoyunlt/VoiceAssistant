"""重排序服务"""
from typing import List

from pydantic import BaseModel
from sentence_transformers import CrossEncoder

from app.core.logging import logger


class RetrievedDocument(BaseModel):
    """检索到的文档"""
    chunk_id: str
    content: str
    score: float = 0.0
    rerank_score: float = 0.0
    metadata: dict = {}


class RerankService:
    """重排序服务"""

    def __init__(self):
        """初始化"""
        # 加载Cross-Encoder模型
        try:
            self.cross_encoder = CrossEncoder(
                'cross-encoder/ms-marco-MiniLM-L-12-v2',
                max_length=512
            )
            logger.info("Cross-Encoder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Cross-Encoder model: {e}")
            self.cross_encoder = None

    async def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: int = 10
    ) -> List[RetrievedDocument]:
        """使用Cross-Encoder重排序

        Args:
            query: 查询文本
            documents: 候选文档列表
            top_k: 返回前k个结果

        Returns:
            重排序后的文档列表
        """
        if not self.cross_encoder:
            logger.warning("Cross-Encoder not available, returning original order")
            return documents[:top_k]

        if not documents:
            return []

        try:
            # 1. 构建query-document对
            pairs = [(query, doc.content) for doc in documents]

            # 2. 计算相关性分数
            scores = self.cross_encoder.predict(pairs)

            # 3. 更新分数
            for doc, score in zip(documents, scores):
                doc.rerank_score = float(score)

            # 4. 按分数排序
            documents_sorted = sorted(
                documents,
                key=lambda x: x.rerank_score,
                reverse=True
            )

            return documents_sorted[:top_k]
        except Exception as e:
            logger.error(f"Rerank error: {e}")
            return documents[:top_k]

    async def rerank_with_llm(
        self,
        query: str,
        documents: List[RetrievedDocument],
        llm_client,
        top_k: int = 10
    ) -> List[RetrievedDocument]:
        """使用LLM重排序（更准确但更慢）

        Args:
            query: 查询文本
            documents: 候选文档列表
            llm_client: LLM客户端
            top_k: 返回前k个结果

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        try:
            # 构建重排序提示词
            doc_texts = []
            for i, doc in enumerate(documents):
                doc_texts.append(f"[{i+1}] {doc.content[:200]}...")

            prompt = f"""Given a query and a list of passages, rank them by relevance to the query.
Return only the passage numbers in order of relevance (most relevant first).

Query: {query}

Passages:
{chr(10).join(doc_texts)}

Ranking (comma-separated numbers):"""

            # 调用LLM
            response = await llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",
                temperature=0.0,
                max_tokens=50
            )

            # 解析排序结果
            ranking_text = response["choices"][0]["message"]["content"].strip()
            rankings = [int(x.strip()) - 1 for x in ranking_text.split(",") if x.strip().isdigit()]

            # 按排序重新组织文档
            reranked_docs = []
            for rank, idx in enumerate(rankings[:top_k]):
                if 0 <= idx < len(documents):
                    doc = documents[idx]
                    doc.rerank_score = 1.0 - (rank / len(rankings))  # 归一化分数
                    reranked_docs.append(doc)

            # 添加未被排序的文档（如果top_k更大）
            if len(reranked_docs) < top_k:
                remaining = [doc for i, doc in enumerate(documents) if i not in rankings]
                reranked_docs.extend(remaining[:top_k - len(reranked_docs)])

            return reranked_docs
        except Exception as e:
            logger.error(f"LLM rerank error: {e}")
            return documents[:top_k]

    async def hybrid_rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        llm_client=None,
        top_k: int = 10,
        cross_encoder_weight: float = 0.7,
        llm_weight: float = 0.3
    ) -> List[RetrievedDocument]:
        """混合重排序（Cross-Encoder + LLM）

        Args:
            query: 查询文本
            documents: 候选文档列表
            llm_client: LLM客户端（可选）
            top_k: 返回前k个结果
            cross_encoder_weight: Cross-Encoder权重
            llm_weight: LLM权重

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        # 1. Cross-Encoder重排序
        ce_reranked = await self.rerank(query, documents, top_k=len(documents))

        # 2. 如果提供了LLM，也用LLM重排序top 20
        if llm_client:
            llm_candidates = ce_reranked[:20]
            llm_reranked = await self.rerank_with_llm(
                query,
                llm_candidates,
                llm_client,
                top_k=len(llm_candidates)
            )

            # 3. 合并分数
            # 为每个文档创建分数映射
            ce_scores = {doc.chunk_id: (i, doc.rerank_score) for i, doc in enumerate(ce_reranked)}
            llm_scores = {doc.chunk_id: (i, doc.rerank_score) for i, doc in enumerate(llm_reranked)}

            # 计算混合分数
            for doc in documents:
                ce_rank, ce_score = ce_scores.get(doc.chunk_id, (len(documents), 0))
                llm_rank, llm_score = llm_scores.get(doc.chunk_id, (len(documents), 0))

                # 归一化排名分数
                ce_rank_score = 1.0 - (ce_rank / len(documents))
                llm_rank_score = 1.0 - (llm_rank / len(documents)) if doc.chunk_id in llm_scores else 0

                # 混合
                doc.rerank_score = (
                    cross_encoder_weight * ce_rank_score +
                    llm_weight * llm_rank_score
                )

            # 排序
            documents_sorted = sorted(
                documents,
                key=lambda x: x.rerank_score,
                reverse=True
            )

            return documents_sorted[:top_k]
        else:
            return ce_reranked[:top_k]
