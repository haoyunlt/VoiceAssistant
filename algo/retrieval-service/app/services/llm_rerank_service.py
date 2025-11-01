"""
LLM-based Re-ranking Service
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMRerankService:
    """LLM重排序服务"""

    def __init__(self, llm_client, batch_size: int = 10):
        self.llm_client = llm_client
        self.batch_size = batch_size

    async def rerank(self, query: str, chunks: list[dict], top_k: int = 10) -> list[dict]:
        """LLM重排序"""
        if not chunks:
            return []

        # 1. 批量评分
        scores = await self._batch_score(query, chunks)

        # 2. 组合chunks和scores
        scored_chunks = list(zip(chunks, scores, strict=False))

        # 3. 排序
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # 4. 返回top-k
        return [chunk for chunk, score in scored_chunks[:top_k]]

    async def _batch_score(self, query: str, chunks: list[dict]) -> list[float]:
        """批量评分"""
        scores = []

        # 分批处理
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_scores = await self._score_batch(query, batch)
            scores.extend(batch_scores)

        return scores

    async def _score_batch(self, query: str, chunks: list[dict]) -> list[float]:
        """对一批chunks评分"""
        # 构建提示
        chunks_text = "\n\n".join(
            [f"[{i}] {chunk.get('content', '')[:300]}" for i, chunk in enumerate(chunks)]
        )

        prompt = f"""Query: {query}

Rate each passage's relevance to the query on a scale of 0-10:

{chunks_text}

Return scores (one per line, just the number):"""

        response = await self.llm_client.chat(
            [
                {"role": "system", "content": "You are a relevance scoring expert."},
                {"role": "user", "content": prompt},
            ]
        )

        # 解析分数
        content = response.get("content", "")
        score_lines = content.strip().split("\n")

        scores = []
        for line in score_lines:
            try:
                score = float(line.strip())
                scores.append(score / 10.0)  # 归一化到0-1
            except Exception:
                scores.append(0.5)  # 默认分数

        # 确保分数数量匹配
        while len(scores) < len(chunks):
            scores.append(0.5)

        return scores[: len(chunks)]

    async def rerank_with_explanation(
        self, query: str, chunks: list[dict], top_k: int = 5
    ) -> list[dict]:
        """带解释的重排序"""
        explanations = []

        for chunk in chunks[: top_k * 2]:  # 评估前2*top_k个
            explanation = await self._explain_relevance(query, chunk.get("content", ""))
            explanations.append(
                {**chunk, "explanation": explanation["explanation"], "score": explanation["score"]}
            )

        # 按分数排序
        explanations.sort(key=lambda x: x["score"], reverse=True)

        return explanations[:top_k]

    async def _explain_relevance(self, query: str, content: str) -> dict[str, Any]:
        """解释相关性"""
        prompt = f"""Query: {query}

Content: {content[:500]}

Explain why this content is relevant (or not) to the query.
Also provide a relevance score (0-1).

Return JSON:
{{
  "score": 0.85,
  "explanation": "explanation here"
}}"""

        response = await self.llm_client.chat([{"role": "user", "content": prompt}])

        import json

        try:
            result = json.loads(response.get("content", "{}"))
            return {"score": result.get("score", 0.5), "explanation": result.get("explanation", "")}
        except Exception:
            return {"score": 0.5, "explanation": ""}
