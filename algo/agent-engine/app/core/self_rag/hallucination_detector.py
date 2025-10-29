"""
幻觉检测模块

检测 Agent 生成的内容是否基于检索结果，防止模型幻觉。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HallucinationLevel(Enum):
    """幻觉等级"""

    NONE = "none"  # 无幻觉，完全基于事实
    LOW = "low"  # 轻微幻觉，大部分基于事实
    MEDIUM = "medium"  # 中等幻觉，部分内容无根据
    HIGH = "high"  # 严重幻觉，大部分内容无根据


@dataclass
class HallucinationReport:
    """幻觉检测报告"""

    level: HallucinationLevel
    confidence: float  # 0-1
    is_grounded: bool  # 是否基于检索结果
    hallucinated_claims: list[str]  # 幻觉声明列表
    grounded_claims: list[str]  # 有根据的声明列表
    reasoning: str
    citations: list[dict[str, str]]  # 引用来源


class HallucinationDetector:
    """
    幻觉检测器

    检测生成内容是否基于检索结果，标注来源引用。

    用法:
        detector = HallucinationDetector(llm_client)

        report = await detector.detect(
            answer="Python was created in 1991.",
            retrieved_docs=["Python is a programming language created by Guido van Rossum..."]
        )

        if report.level in [HallucinationLevel.MEDIUM, HallucinationLevel.HIGH]:
            # 触发警告或人工审核
            pass
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "gpt-4",
        hallucination_threshold: float = 0.3,
        enable_citations: bool = True,
    ):
        """
        初始化幻觉检测器

        Args:
            llm_client: LLM 客户端
            model: 使用的模型（建议用 GPT-4 以提高准确性）
            hallucination_threshold: 幻觉阈值 (0-1)
            enable_citations: 是否生成引用
        """
        self.llm_client = llm_client
        self.model = model
        self.hallucination_threshold = hallucination_threshold
        self.enable_citations = enable_citations

        logger.info(
            f"HallucinationDetector initialized (model={model}, "
            f"threshold={hallucination_threshold})"
        )

    async def detect(
        self,
        answer: str,
        retrieved_docs: list[str],
        query: str | None = None,
    ) -> HallucinationReport:
        """
        检测幻觉

        Args:
            answer: Agent 生成的答案
            retrieved_docs: 检索到的文档
            query: 原始查询（可选）

        Returns:
            幻觉检测报告
        """
        if not retrieved_docs:
            # 没有检索结果，无法验证
            return HallucinationReport(
                level=HallucinationLevel.HIGH,
                confidence=0.9,
                is_grounded=False,
                hallucinated_claims=[answer],
                grounded_claims=[],
                reasoning="No retrieved documents to verify against",
                citations=[],
            )

        # 使用 LLM 检测
        return await self._detect_with_llm(answer, retrieved_docs, query)

    async def _detect_with_llm(
        self, answer: str, retrieved_docs: list[str], query: str | None
    ) -> HallucinationReport:
        """使用 LLM 检测幻觉"""
        docs_text = self._format_documents(retrieved_docs)

        prompt = f"""你是一个事实核查专家。请检查以下答案是否基于提供的文档，是否存在幻觉（虚构的、无根据的内容）。

{f"查询: {query}" if query else ""}

答案:
{answer}

参考文档:
{docs_text}

请以 JSON 格式输出检测结果:
{{
  "level": "none|low|medium|high",
  "confidence": 0.0-1.0,
  "is_grounded": true|false,
  "hallucinated_claims": ["幻觉声明1", "幻觉声明2", ...],
  "grounded_claims": ["有根据的声明1", "有根据的声明2", ...],
  "reasoning": "检测理由",
  "citations": [
    {{"claim": "声明", "source": "文档X", "quote": "引用原文"}}
  ]
}}

评估标准:
- none: 答案完全基于文档，无幻觉
- low: 答案大部分基于文档，有轻微推理或常识补充
- medium: 答案部分内容无法在文档中找到依据
- high: 答案大部分内容无根据，可能是虚构的

is_grounded: 答案整体是否基于检索结果（幻觉比例 < 30%）
"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            result = response  # 假设返回 JSON
            return HallucinationReport(
                level=HallucinationLevel(result.get("level", "medium")),
                confidence=float(result.get("confidence", 0.5)),
                is_grounded=result.get("is_grounded", False),
                hallucinated_claims=result.get("hallucinated_claims", []),
                grounded_claims=result.get("grounded_claims", []),
                reasoning=result.get("reasoning", ""),
                citations=result.get("citations", []),
            )

        except Exception as e:
            logger.error(f"Error in hallucination detection: {e}")
            # 降级到规则检测
            return self._detect_with_rules(answer, retrieved_docs)

    def _detect_with_rules(
        self, answer: str, retrieved_docs: list[str]
    ) -> HallucinationReport:
        """使用规则检测幻觉（快速、无成本）"""
        # 将答案拆分为句子
        sentences = [s.strip() for s in answer.split(".") if s.strip()]

        grounded_sentences = []
        hallucinated_sentences = []

        for sentence in sentences:
            # 检查句子是否在任何文档中有支撑
            is_grounded = self._is_sentence_grounded(sentence, retrieved_docs)

            if is_grounded:
                grounded_sentences.append(sentence)
            else:
                hallucinated_sentences.append(sentence)

        # 计算幻觉比例
        total_sentences = len(sentences)
        hallucination_ratio = (
            len(hallucinated_sentences) / total_sentences if total_sentences > 0 else 0.0
        )

        # 判断幻觉等级
        if hallucination_ratio == 0:
            level = HallucinationLevel.NONE
        elif hallucination_ratio < 0.3:
            level = HallucinationLevel.LOW
        elif hallucination_ratio < 0.6:
            level = HallucinationLevel.MEDIUM
        else:
            level = HallucinationLevel.HIGH

        is_grounded = hallucination_ratio < self.hallucination_threshold

        return HallucinationReport(
            level=level,
            confidence=0.7,  # 规则检测的置信度固定
            is_grounded=is_grounded,
            hallucinated_claims=hallucinated_sentences,
            grounded_claims=grounded_sentences,
            reasoning=f"Rule-based detection: {hallucination_ratio:.1%} hallucination rate",
            citations=[],
        )

    def _is_sentence_grounded(self, sentence: str, documents: list[str]) -> bool:
        """检查句子是否在文档中有支撑"""
        sentence_lower = sentence.lower()
        sentence_terms = set(sentence_lower.split())

        for doc in documents:
            doc_lower = doc.lower()
            doc_terms = set(doc_lower.split())

            # 计算词重叠率
            overlap = sentence_terms & doc_terms
            overlap_ratio = len(overlap) / len(sentence_terms) if sentence_terms else 0.0

            # 如果重叠率 > 60%，认为有支撑
            if overlap_ratio >= 0.6:
                return True

        return False

    def _format_documents(self, documents: list[str]) -> str:
        """格式化文档"""
        formatted = []
        for i, doc in enumerate(documents, 1):
            doc_preview = doc[:300] + "..." if len(doc) > 300 else doc
            formatted.append(f"文档{i}:\n{doc_preview}")
        return "\n\n".join(formatted)

    async def add_citations(
        self, answer: str, report: HallucinationReport
    ) -> str:
        """
        为答案添加引用标注

        Args:
            answer: 原始答案
            report: 幻觉检测报告

        Returns:
            带引用的答案
        """
        if not self.enable_citations or not report.citations:
            return answer

        # 为每个有根据的声明添加引用
        annotated_answer = answer

        for citation in report.citations:
            claim = citation.get("claim", "")
            source = citation.get("source", "")

            if claim in annotated_answer:
                # 添加上标引用
                annotated_answer = annotated_answer.replace(
                    claim, f"{claim} [{source}]"
                )

        return annotated_answer

    async def verify_and_correct(
        self,
        answer: str,
        retrieved_docs: list[str],
        query: str | None = None,
    ) -> dict[str, Any]:
        """
        检测幻觉并尝试修正

        Args:
            answer: 原始答案
            retrieved_docs: 检索文档
            query: 原始查询

        Returns:
            包含原始答案、检测报告、修正建议的字典
        """
        # 检测幻觉
        report = await self.detect(answer, retrieved_docs, query)

        # 如果有严重幻觉，生成修正建议
        correction_suggestion = None
        if report.level in [HallucinationLevel.MEDIUM, HallucinationLevel.HIGH]:
            correction_suggestion = await self._suggest_correction(
                answer, retrieved_docs, report
            )

        return {
            "original_answer": answer,
            "report": report,
            "correction_suggestion": correction_suggestion,
            "should_review": report.level
            in [HallucinationLevel.MEDIUM, HallucinationLevel.HIGH],
        }

    async def _suggest_correction(
        self, answer: str, retrieved_docs: list[str], report: HallucinationReport
    ) -> str:
        """建议修正"""
        docs_text = self._format_documents(retrieved_docs)

        prompt = f"""以下答案被检测出存在幻觉。请基于提供的文档重写答案，确保所有声明都有根据。

原答案:
{answer}

幻觉内容:
{', '.join(report.hallucinated_claims)}

参考文档:
{docs_text}

请输出修正后的答案，确保:
1. 所有声明都基于文档
2. 删除或修正幻觉内容
3. 保持答案的完整性和流畅性
"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error in correction suggestion: {e}")
            return answer

