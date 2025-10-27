"""查询改写服务"""
from typing import List, Optional

from pydantic import BaseModel

from app.core.logging import logger


class RewrittenQuery(BaseModel):
    """改写后的查询"""
    original: str
    rewritten: str
    confidence: float = 1.0


class QueryRewriterService:
    """查询改写服务"""

    def __init__(self, llm_client):
        """初始化

        Args:
            llm_client: LLM客户端
        """
        self.llm_client = llm_client

    async def rewrite_query(
        self,
        query: str,
        context: Optional[List[str]] = None
    ) -> RewrittenQuery:
        """改写查询

        Args:
            query: 原始查询
            context: 对话上下文（可选）

        Returns:
            改写后的查询
        """
        try:
            # 构建改写提示词
            prompt = self._build_rewrite_prompt(query, context)

            # 调用LLM改写
            response = await self.llm_client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a query rewriter that improves search queries for better retrieval results."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="gpt-3.5-turbo",
                temperature=0.3
            )

            rewritten = response["choices"][0]["message"]["content"].strip()

            # 清理改写结果
            rewritten = self._clean_rewritten_query(rewritten)

            return RewrittenQuery(
                original=query,
                rewritten=rewritten,
                confidence=1.0
            )
        except Exception as e:
            logger.error(f"Query rewriting error: {e}")
            # 失败时返回原查询
            return RewrittenQuery(
                original=query,
                rewritten=query,
                confidence=0.0
            )

    def _build_rewrite_prompt(
        self,
        query: str,
        context: Optional[List[str]] = None
    ) -> str:
        """构建改写提示词

        Args:
            query: 查询
            context: 对话上下文

        Returns:
            提示词
        """
        prompt = f"""请改写以下查询，使其更适合语义检索：

原始查询: {query}
"""

        if context:
            prompt += f"\n对话上下文:\n" + "\n".join(f"- {c}" for c in context[-3:])  # 只用最近3轮

        prompt += """

改写要求：
1. 补全缺失的主语或宾语
2. 将口语化表达转为书面语
3. 明确查询意图
4. 保留关键信息
5. 展开代词指代（如"它"、"这个"等）
6. 不要添加额外信息

只返回改写后的查询，不要其他内容。

改写后的查询："""

        return prompt

    def _clean_rewritten_query(self, query: str) -> str:
        """清理改写结果

        Args:
            query: 改写后的查询

        Returns:
            清理后的查询
        """
        # 去除首尾引号
        query = query.strip().strip('"\'""''')

        # 去除"改写后的查询："等前缀
        prefixes = ["改写后的查询：", "改写后的查询:", "改写：", "改写:", "Rewritten query:", "Rewritten:"]
        for prefix in prefixes:
            if query.startswith(prefix):
                query = query[len(prefix):].strip()

        return query

    async def expand_with_synonyms(
        self,
        query: str
    ) -> List[str]:
        """使用同义词扩展查询

        Args:
            query: 原始查询

        Returns:
            扩展后的查询列表
        """
        try:
            prompt = f"""为以下查询生成3个同义改写，每行一个：

原始查询: {query}

要求：
1. 保持语义相同
2. 使用不同的表达方式
3. 包含同义词
4. 每行一个查询，不要编号

同义查询："""

            response = await self.llm_client.chat(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=200
            )

            expanded_text = response["choices"][0]["message"]["content"].strip()

            # 解析每行
            expanded_queries = [query]  # 包含原查询
            for line in expanded_text.split('\n'):
                line = line.strip()
                # 去除可能的编号
                line = line.lstrip('0123456789.-) ')
                if line and line != query:
                    expanded_queries.append(line)

            return expanded_queries[:4]  # 最多返回4个
        except Exception as e:
            logger.error(f"Query expansion error: {e}")
            return [query]

    async def decompose_query(
        self,
        query: str
    ) -> List[str]:
        """分解复杂查询为多个子查询

        Args:
            query: 复杂查询

        Returns:
            子查询列表
        """
        try:
            prompt = f"""将以下复杂查询分解为多个简单的子查询，每行一个：

复杂查询: {query}

要求：
1. 每个子查询回答查询的一部分
2. 子查询应该独立且完整
3. 保留所有关键信息
4. 每行一个子查询，不要编号

子查询："""

            response = await self.llm_client.chat(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="gpt-3.5-turbo",
                temperature=0.3,
                max_tokens=200
            )

            decomposed_text = response["choices"][0]["message"]["content"].strip()

            # 解析每行
            subqueries = []
            for line in decomposed_text.split('\n'):
                line = line.strip()
                # 去除可能的编号
                line = line.lstrip('0123456789.-) ')
                if line:
                    subqueries.append(line)

            return subqueries if subqueries else [query]
        except Exception as e:
            logger.error(f"Query decomposition error: {e}")
            return [query]
