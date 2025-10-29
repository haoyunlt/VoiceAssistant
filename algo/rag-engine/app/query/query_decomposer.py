"""
Query Decomposer - 查询分解器

将复杂查询分解为多个子查询，用于并行检索
"""

import json
import logging

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """查询分解器"""

    def __init__(self, llm_client):
        """
        初始化查询分解器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("Query decomposer initialized")

    async def decompose(
        self, query: str, max_sub_queries: int = 4, query_analysis: dict | None = None
    ) -> list[str]:
        """
        分解查询

        Args:
            query: 原始查询
            max_sub_queries: 最大子查询数
            query_analysis: 查询分析结果（可选）

        Returns:
            子查询列表
        """
        # 检查是否需要分解
        if not await self._should_decompose(query, query_analysis):
            logger.info(f"Query does not need decomposition: {query[:50]}...")
            return [query]

        # 使用 LLM 分解查询
        sub_queries = await self._decompose_with_llm(query, max_sub_queries, query_analysis)

        logger.info(f"Decomposed query into {len(sub_queries)} sub-queries")
        return sub_queries

    async def _should_decompose(self, query: str, query_analysis: dict | None) -> bool:
        """
        判断是否需要分解

        Args:
            query: 查询
            query_analysis: 查询分析结果

        Returns:
            是否需要分解
        """
        # 基于查询分析
        if query_analysis:
            complexity = query_analysis.get("complexity", 5)
            query_type = query_analysis.get("type", "")
            requires_multiple = query_analysis.get("requires_multiple_sources", False)

            # 复杂度高或需要多源信息时分解
            if complexity >= 7 or requires_multiple:
                return True

            # 特定查询类型需要分解
            if query_type in ["multi_hop", "comparison", "aggregation"]:
                return True

        # 基于简单规则
        # 包含多个问题词或连接词
        question_words = ["what", "how", "why", "when", "where", "who", "什么", "如何", "为什么"]
        conjunctions = ["and", "or", "以及", "或", "还有"]

        question_count = sum(1 for word in question_words if word in query.lower())
        conjunction_count = sum(1 for word in conjunctions if word in query.lower())

        if question_count > 1 or conjunction_count > 0:
            return True

        # 查询长度较长
        return len(query) > 100

    async def _decompose_with_llm(
        self, query: str, max_sub_queries: int, query_analysis: dict | None
    ) -> list[str]:
        """
        使用 LLM 分解查询

        Args:
            query: 原始查询
            max_sub_queries: 最大子查询数
            query_analysis: 查询分析结果

        Returns:
            子查询列表
        """
        # 构建提示
        analysis_context = ""
        if query_analysis:
            key_concepts = query_analysis.get("key_concepts", [])
            if key_concepts:
                analysis_context = f"\n关键概念: {', '.join(key_concepts)}"

        prompt = f"""将以下复杂查询分解为 2-{max_sub_queries} 个更简单的子查询。
每个子查询应该是独立的、可以单独回答的问题。{analysis_context}

原始查询: {query}

要求:
1. 子查询之间应该有逻辑关联
2. 每个子查询都明确且可回答
3. 子查询的答案组合可以回答原始查询
4. 以 JSON 数组格式返回

JSON 格式:
["子查询1", "子查询2", ...]

JSON:"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt, temperature=0.5, max_tokens=500
            )

            # 解析 JSON
            # 尝试提取 JSON 部分
            response = response.strip()
            if response.startswith("```"):
                # 移除代码块标记
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            sub_queries = json.loads(response)

            # 验证结果
            if isinstance(sub_queries, list) and all(isinstance(q, str) for q in sub_queries):
                # 限制子查询数量
                sub_queries = sub_queries[:max_sub_queries]
                return sub_queries if sub_queries else [query]
            else:
                logger.warning(f"Invalid sub-queries format: {response}")
                return [query]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sub-queries JSON: {e}\nResponse: {response}")
            # 回退：按标点符号分割
            return self._simple_split(query)
        except Exception as e:
            logger.error(f"Query decomposition failed: {e}")
            return [query]

    def _simple_split(self, query: str) -> list[str]:
        """
        简单分割（回退方案）

        Args:
            query: 查询

        Returns:
            分割后的查询列表
        """
        import re

        # 按句子分割
        sentences = re.split(r"[。？！?!]", query)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 如果只有一句，尝试按连接词分割
        if len(sentences) == 1:
            for conjunction in ["and", "以及", "还有", "以及"]:
                if conjunction in query.lower():
                    parts = query.split(conjunction)
                    sentences = [p.strip() for p in parts if p.strip()]
                    break

        return sentences if sentences else [query]

    async def merge_answers(
        self, sub_queries: list[str], sub_answers: list[str], original_query: str
    ) -> str:
        """
        合并子查询的答案

        Args:
            sub_queries: 子查询列表
            sub_answers: 子答案列表
            original_query: 原始查询

        Returns:
            合并后的答案
        """
        # 构建合并提示
        qa_pairs = "\n\n".join(
            [
                f"问题{i+1}: {q}\n答案{i+1}: {a}"
                for i, (q, a) in enumerate(zip(sub_queries, sub_answers, strict=False))
            ]
        )

        prompt = f"""基于以下子问题的答案，综合回答原始问题。

原始问题: {original_query}

{qa_pairs}

请综合以上答案，给出完整、连贯的回复:"""

        try:
            merged_answer = await self.llm_client.generate(
                prompt=prompt, temperature=0.7, max_tokens=1000
            )
            return merged_answer.strip()
        except Exception as e:
            logger.error(f"Answer merging failed: {e}")
            # 回退：简单拼接
            return "\n\n".join([f"{q}: {a}" for q, a in zip(sub_queries, sub_answers, strict=False)])

