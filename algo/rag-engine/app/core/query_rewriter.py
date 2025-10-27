"""查询改写器 - HyDE, Multi-Query扩展."""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class QueryRewriter:
    """查询改写器."""

    def __init__(
        self,
        llm_client: Optional[AsyncOpenAI] = None,
        model: str = "gpt-3.5-turbo",
    ):
        """
        初始化查询改写器.

        Args:
            llm_client: OpenAI客户端
            model: 使用的模型
        """
        self.llm_client = llm_client
        self.model = model

    async def rewrite_multi_query(self, query: str, num_queries: int = 3) -> List[str]:
        """
        多查询扩展 - 生成多个相关查询.

        Args:
            query: 原始查询
            num_queries: 生成查询数量

        Returns:
            查询列表 (包含原始查询)
        """
        if not self.llm_client:
            return [query]

        prompt = f"""Given the following user query, generate {num_queries-1} alternative queries that capture different aspects or phrasings of the same information need.

User Query: {query}

Requirements:
1. Each alternative should be semantically related but use different words
2. Cover different aspects or interpretations of the original query
3. Keep queries concise and clear

Generate {num_queries-1} alternative queries (one per line):"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates alternative search queries."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()
            alternative_queries = [q.strip() for q in content.split("\n") if q.strip()]

            # 包含原始查询
            all_queries = [query] + alternative_queries[:num_queries - 1]
            return all_queries

        except Exception as e:
            logger.error(f"Multi-query rewriting failed: {e}")
            return [query]

    async def rewrite_hyde(self, query: str) -> str:
        """
        HyDE (Hypothetical Document Embeddings) - 生成假设答案.

        生成一个假设的答案文档，然后用这个文档进行检索，
        这样可以更好地匹配到实际的答案文档。

        Args:
            query: 用户查询

        Returns:
            假设答案文本
        """
        if not self.llm_client:
            return query

        prompt = f"""Given the following question, write a detailed and informative answer as if you were answering from a knowledge base document.

Question: {query}

Write a hypothetical answer (2-3 paragraphs):"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a knowledgeable assistant writing informative answers."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=300,
            )

            hypothetical_answer = response.choices[0].message.content.strip()
            return hypothetical_answer

        except Exception as e:
            logger.error(f"HyDE rewriting failed: {e}")
            return query

    async def rewrite_query(
        self,
        query: str,
        method: str = "multi",
        num_queries: int = 3,
    ) -> List[str]:
        """
        统一的查询改写接口.

        Args:
            query: 原始查询
            method: 改写方法 (multi/hyde/none)
            num_queries: 多查询扩展数量 (仅用于multi)

        Returns:
            改写后的查询列表
        """
        if method == "multi":
            return await self.rewrite_multi_query(query, num_queries)
        elif method == "hyde":
            hyde_result = await self.rewrite_hyde(query)
            return [hyde_result]
        elif method == "none":
            return [query]
        else:
            logger.warning(f"Unknown rewrite method: {method}, using original query")
            return [query]

    async def decompose_query(self, query: str) -> List[str]:
        """
        查询分解 - 将复杂查询分解为多个子查询.

        适用于包含多个问题或复杂逻辑的查询。

        Args:
            query: 复杂查询

        Returns:
            子查询列表
        """
        if not self.llm_client:
            return [query]

        prompt = f"""Analyze the following query and decompose it into simpler sub-queries if it contains multiple questions or complex logic.

Query: {query}

If the query is simple, return it as is. If it's complex, break it down into 2-4 simpler sub-queries.

Sub-queries (one per line):"""

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that decomposes complex queries."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()
            sub_queries = [q.strip() for q in content.split("\n") if q.strip()]

            return sub_queries if sub_queries else [query]

        except Exception as e:
            logger.error(f"Query decomposition failed: {e}")
            return [query]
