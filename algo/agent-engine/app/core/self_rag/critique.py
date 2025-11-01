"""
检索质量评估模块

使用小模型或规则评估检索结果的相关性和充分性。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RelevanceLevel(Enum):
    """相关性等级"""

    HIGH = "high"  # 高度相关
    MEDIUM = "medium"  # 中等相关
    LOW = "low"  # 低相关
    IRRELEVANT = "irrelevant"  # 不相关


@dataclass
class RetrievalAssessment:
    """检索评估结果"""

    relevance: RelevanceLevel
    confidence: float  # 0-1
    is_sufficient: bool  # 是否充分
    need_rewrite: bool  # 是否需要重写查询
    reasoning: str  # 评估理由
    suggested_rewrite: str | None = None  # 重写建议


class RetrievalCritic:
    """
    检索质量评估器

    用法:
        critic = RetrievalCritic(llm_client)

        # 评估检索结果
        assessment = await critic.assess_relevance(
            query="What is Python?",
            documents=["Python is a programming language...", "..."]
        )

        if assessment.need_rewrite:
            new_query = assessment.suggested_rewrite
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "gpt-3.5-turbo",
        relevance_threshold: float = 0.6,
        sufficiency_threshold: int = 3,
    ):
        """
        初始化检索评估器

        Args:
            llm_client: LLM 客户端
            model: 使用的模型（建议用小模型以降低成本）
            relevance_threshold: 相关性阈值 (0-1)
            sufficiency_threshold: 最少相关文档数
        """
        self.llm_client = llm_client
        self.model = model
        self.relevance_threshold = relevance_threshold
        self.sufficiency_threshold = sufficiency_threshold

        logger.info(
            f"RetrievalCritic initialized (model={model}, "
            f"relevance_threshold={relevance_threshold})"
        )

    async def assess_relevance(
        self, query: str, documents: list[str], use_llm: bool = True
    ) -> RetrievalAssessment:
        """
        评估检索结果的相关性

        Args:
            query: 查询文本
            documents: 检索到的文档列表
            use_llm: 是否使用 LLM 评估（否则用规则）

        Returns:
            评估结果
        """
        if not documents:
            return RetrievalAssessment(
                relevance=RelevanceLevel.IRRELEVANT,
                confidence=1.0,
                is_sufficient=False,
                need_rewrite=True,
                reasoning="No documents retrieved",
                suggested_rewrite=await self._suggest_rewrite(query),
            )

        if use_llm:
            return await self._assess_with_llm(query, documents)
        else:
            return self._assess_with_rules(query, documents)

    async def _assess_with_llm(self, query: str, documents: list[str]) -> RetrievalAssessment:
        """使用 LLM 评估检索质量"""
        # 限制文档数量以节省成本
        docs_sample = documents[: min(5, len(documents))]

        prompt = f"""你是一个检索质量评估专家。请评估以下检索结果对于给定查询的相关性和充分性。

查询: {query}

检索到的文档:
{self._format_documents(docs_sample)}

请以 JSON 格式输出评估结果:
{{
  "relevance": "high|medium|low|irrelevant",
  "confidence": 0.0-1.0,
  "is_sufficient": true|false,
  "need_rewrite": true|false,
  "reasoning": "评估理由",
  "suggested_rewrite": "如果需要重写,提供新的查询"
}}

评估标准:
- high: 文档直接回答了查询,内容准确且完整
- medium: 文档部分相关,但可能不够详细或有偏差
- low: 文档相关性较低,只是间接提及
- irrelevant: 文档完全不相关

is_sufficient: 检索结果是否足够回答查询（至少{self.sufficiency_threshold}个相关文档）
need_rewrite: 如果检索质量低,是否建议重写查询以获得更好结果
"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            result = response  # 假设返回 JSON
            return RetrievalAssessment(
                relevance=RelevanceLevel(result.get("relevance", "low")),
                confidence=float(result.get("confidence", 0.5)),
                is_sufficient=result.get("is_sufficient", False),
                need_rewrite=result.get("need_rewrite", False),
                reasoning=result.get("reasoning", ""),
                suggested_rewrite=result.get("suggested_rewrite"),
            )

        except Exception as e:
            logger.error(f"Error in LLM-based assessment: {e}")
            # 降级到规则评估
            return self._assess_with_rules(query, documents)

    def _assess_with_rules(self, query: str, documents: list[str]) -> RetrievalAssessment:
        """使用规则评估检索质量（快速、无成本）"""
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        relevant_docs = 0
        total_relevance_score = 0.0

        for doc in documents:
            doc_lower = doc.lower()
            doc_terms = set(doc_lower.split())

            # 计算词重叠率
            overlap = query_terms & doc_terms
            relevance_score = len(overlap) / len(query_terms) if query_terms else 0.0

            if relevance_score >= self.relevance_threshold:
                relevant_docs += 1
                total_relevance_score += relevance_score

        avg_relevance = total_relevance_score / len(documents) if documents else 0.0

        # 判断相关性等级
        if avg_relevance >= 0.7:
            relevance = RelevanceLevel.HIGH
        elif avg_relevance >= 0.5:
            relevance = RelevanceLevel.MEDIUM
        elif avg_relevance >= 0.3:
            relevance = RelevanceLevel.LOW
        else:
            relevance = RelevanceLevel.IRRELEVANT

        is_sufficient = relevant_docs >= self.sufficiency_threshold
        need_rewrite = relevance in [RelevanceLevel.LOW, RelevanceLevel.IRRELEVANT]

        reasoning = (
            f"Rule-based assessment: {relevant_docs}/{len(documents)} relevant docs, "
            f"avg relevance score: {avg_relevance:.2f}"
        )

        return RetrievalAssessment(
            relevance=relevance,
            confidence=0.7,  # 规则评估的置信度固定
            is_sufficient=is_sufficient,
            need_rewrite=need_rewrite,
            reasoning=reasoning,
            suggested_rewrite=None,  # 规则评估不提供重写建议
        )

    async def _suggest_rewrite(self, original_query: str) -> str:
        """建议查询重写"""
        prompt = f"""请改写以下查询以获得更好的检索结果:

原查询: {original_query}

改写建议:
1. 使用更具体的关键词
2. 添加上下文信息
3. 使用同义词或相关术语

只输出改写后的查询,不要解释。"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error in query rewrite: {e}")
            return original_query

    def _format_documents(self, documents: list[str]) -> str:
        """格式化文档用于展示"""
        formatted = []
        for i, doc in enumerate(documents, 1):
            # 限制文档长度
            doc_preview = doc[:200] + "..." if len(doc) > 200 else doc
            formatted.append(f"{i}. {doc_preview}")
        return "\n\n".join(formatted)

    async def evaluate_retrieval_strategy(
        self, query: str, results_by_strategy: dict[str, list[str]]
    ) -> str:
        """
        评估不同检索策略的效果

        Args:
            query: 查询文本
            results_by_strategy: 不同策略的检索结果
                例如: {"dense": [...], "sparse": [...], "hybrid": [...]}

        Returns:
            最佳策略名称
        """
        assessments = {}

        for strategy, documents in results_by_strategy.items():
            assessment = await self.assess_relevance(query, documents, use_llm=False)
            assessments[strategy] = assessment

            logger.debug(
                f"Strategy '{strategy}': relevance={assessment.relevance.value}, "
                f"sufficient={assessment.is_sufficient}"
            )

        # 选择最佳策略
        best_strategy = max(
            assessments.keys(),
            key=lambda s: (
                assessments[s].is_sufficient,
                assessments[s].confidence,
            ),
        )

        logger.info(f"Best retrieval strategy for query: {best_strategy}")
        return best_strategy
