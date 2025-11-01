"""查询理解服务"""

import logging

import httpx

from app.core.config import settings
from app.models.rag import QueryExpansionResult

logger = logging.getLogger(__name__)


class QueryService:
    """查询理解服务"""

    def __init__(self):
        self.model_adapter_url = settings.MODEL_ADAPTER_URL

    async def expand_query(self, query: str, num_expansions: int = 3) -> QueryExpansionResult:
        """
        查询扩展

        使用LLM生成查询的多个变体

        Args:
            query: 原始查询
            num_expansions: 扩展数量

        Returns:
            查询扩展结果
        """
        try:
            prompt = f"""Given the user query: "{query}"

Generate {num_expansions} alternative phrasings or related queries that would help retrieve relevant information.

Format your response as a JSON array of strings, like:
["alternative query 1", "alternative query 2", "alternative query 3"]

Alternative queries:"""

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.model_adapter_url}/api/v1/chat/completions",
                    json={
                        "model": settings.DEFAULT_LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 500,
                    },
                )

                response.raise_for_status()
                data = response.json()

                # 解析LLM响应
                content = data["choices"][0]["message"]["content"]

                # 简单解析（实际应该更robust）
                import json

                try:
                    expanded_queries = json.loads(content)
                except Exception:
                    # 如果JSON解析失败，按行分割
                    expanded_queries = [
                        line.strip()
                        for line in content.split("\n")
                        if line.strip() and not line.startswith("[")
                    ][:num_expansions]

                return QueryExpansionResult(
                    original_query=query,
                    expanded_queries=expanded_queries,
                )

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            # 失败时返回原查询
            return QueryExpansionResult(
                original_query=query,
                expanded_queries=[],
            )

    async def extract_keywords(self, query: str) -> list[str]:
        """
        提取关键词

        Args:
            query: 查询

        Returns:
            关键词列表
        """
        # 简单实现：分词
        # 实际应该使用NLP工具（如jieba、spaCy等）
        keywords = query.split()
        return [kw for kw in keywords if len(kw) > 2]
