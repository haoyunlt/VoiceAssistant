"""
Hallucination Detector - 幻觉检测器

检测生成答案中的幻觉内容
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


class HallucinationDetector:
    """幻觉检测器"""

    def __init__(self, llm_client, use_nli: bool = False):
        """
        初始化幻觉检测器

        Args:
            llm_client: LLM 客户端
            use_nli: 使用 NLI 模型（需要额外安装）
        """
        self.llm_client = llm_client
        self.use_nli = use_nli

        # NLI 模型（可选）
        if use_nli:
            try:
                from transformers import pipeline

                self.nli_model = pipeline(
                    "text-classification", model="microsoft/deberta-v3-base-mnli"
                )
                logger.info("NLI model loaded for hallucination detection")
            except Exception as e:
                logger.warning(f"Failed to load NLI model: {e}")
                self.use_nli = False

        logger.info(f"Hallucination detector initialized (NLI: {self.use_nli})")

    async def detect(
        self, answer: str, context: str, query: str, _threshold: float = 0.7
    ) -> dict[str, any]:
        """
        检测幻觉

        Args:
            answer: 生成的答案
            context: 检索的上下文
            query: 原始查询
            threshold: 置信度阈值

        Returns:
            检测结果
        """
        # 方法 1: LLM-based 检测
        llm_result = await self._detect_with_llm(answer, context, query)

        # 方法 2: NLI-based 检测（如果启用）
        nli_result = None
        if self.use_nli:
            nli_result = self._detect_with_nli(answer, context)

        # 方法 3: 规则检测
        rule_result = self._detect_with_rules(answer, context)

        # 综合判断
        has_hallucination = llm_result.get("has_hallucination", False)
        confidence = llm_result.get("confidence", 0.5)

        if nli_result:  # noqa: SIM102
            # 结合 NLI 结果
            if nli_result["has_hallucination"]:
                has_hallucination = True
                confidence = max(confidence, nli_result["confidence"])

        if rule_result["has_hallucination"]:
            # 规则检测到明确的幻觉
            has_hallucination = True

        result = {
            "has_hallucination": has_hallucination,
            "confidence": confidence,
            "reasons": [],
            "llm_result": llm_result,
            "nli_result": nli_result,
            "rule_result": rule_result,
        }

        # 收集原因
        if llm_result.get("has_hallucination"):
            result["reasons"].append(f"LLM: {llm_result.get('reason', '')}")
        if nli_result and nli_result.get("has_hallucination"):
            result["reasons"].append("NLI: 蕴含关系矛盾")
        if rule_result["has_hallucination"]:
            result["reasons"].extend(rule_result["reasons"])

        logger.info(f"Hallucination detection: {has_hallucination} (confidence: {confidence:.2f})")
        return result

    async def _detect_with_llm(self, answer: str, context: str, query: str) -> dict[str, any]:
        """使用 LLM 检测幻觉"""
        prompt = f"""作为一个事实核查器，请判断答案是否与提供的上下文一致，是否存在幻觉内容。

查询: {query}

上下文:
{context[:1500]}

答案:
{answer}

请以 JSON 格式回答:
{{
    "has_hallucination": true/false,
    "confidence": 0.0-1.0,
    "reason": "简要说明",
    "supported_claims": ["支持的声明"],
    "unsupported_claims": ["不支持的声明"]
}}

JSON:"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt, temperature=0.2, max_tokens=500
            )

            # 解析 JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            result = json.loads(response)
            return result

        except Exception as e:
            logger.error(f"LLM hallucination detection failed: {e}")
            return {
                "has_hallucination": False,
                "confidence": 0.5,
                "reason": "Detection failed",
            }

    def _detect_with_nli(self, answer: str, context: str) -> dict[str, any]:
        """使用 NLI 模型检测幻觉"""
        if not self.use_nli:
            return None

        try:
            # 将答案拆分为句子
            answer_sentences = self._split_sentences(answer)
            context_text = context[:1000]  # 限制上下文长度

            unsupported_count = 0
            total_count = len(answer_sentences)

            for sentence in answer_sentences:
                # 检查句子是否被上下文蕴含
                result = self.nli_model(f"{context_text} [SEP] {sentence}")
                label = result[0]["label"]

                # 如果 label 是 "CONTRADICTION" 或 "NEUTRAL"，认为不支持
                if label in ["CONTRADICTION", "NEUTRAL"]:
                    unsupported_count += 1

            # 如果超过 30% 的句子不支持，认为存在幻觉
            unsupported_ratio = unsupported_count / max(total_count, 1)
            has_hallucination = unsupported_ratio > 0.3

            return {
                "has_hallucination": has_hallucination,
                "confidence": unsupported_ratio,
                "unsupported_count": unsupported_count,
                "total_count": total_count,
            }

        except Exception as e:
            logger.error(f"NLI hallucination detection failed: {e}")
            return None

    def _detect_with_rules(self, answer: str, context: str) -> dict[str, any]:
        """使用规则检测幻觉"""
        reasons = []
        has_hallucination = False

        # 规则 1: 答案中提到"我不知道"/"无法回答"等，但实际提供了答案
        uncertainty_phrases = ["不知道", "无法回答", "不确定", "没有信息"]
        if any(phrase in answer for phrase in uncertainty_phrases):  # noqa: SIM102
            # 检查是否还提供了具体答案
            if len(answer.split()) > 20:  # 答案较长
                has_hallucination = True
                reasons.append("答案前后矛盾：表达不确定但提供了答案")

        # 规则 2: 答案中出现了上下文中不存在的关键数字
        answer_numbers = set(re.findall(r"\b\d+\.?\d*\b", answer))
        context_numbers = set(re.findall(r"\b\d+\.?\d*\b", context))
        unique_numbers = answer_numbers - context_numbers

        # 过滤掉常见数字（如日期）
        unique_numbers = {
            n for n in unique_numbers if not (n in ["2023", "2024", "2025"] or int(float(n)) < 10)
        }

        if len(unique_numbers) > 2:
            has_hallucination = True
            reasons.append(f"答案包含上下文中不存在的数字: {unique_numbers}")

        # 规则 3: 答案过于笼统，没有引用上下文
        if len(answer) > 100:
            # 检查是否有任何上下文词汇出现在答案中
            context_words = set(context.split()[:200])  # 上下文前200词
            answer_words = set(answer.split())
            overlap = len(context_words & answer_words)

            if overlap < 5:
                has_hallucination = True
                reasons.append("答案与上下文重叠度过低，可能是通用回答")

        return {"has_hallucination": has_hallucination, "reasons": reasons}

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        # 简单分割
        sentences = re.split(r"[。！？.!?]", text)
        return [s.strip() for s in sentences if s.strip()]

    async def verify_facts(self, answer: str, sources: list[dict]) -> dict[str, any]:
        """
        验证答案中的事实

        Args:
            answer: 答案
            sources: 源文档列表

        Returns:
            验证结果
        """
        # 提取答案中的声明
        claims = self._extract_claims(answer)

        # 为每个声明查找支持
        verified_claims = []
        for claim in claims:
            support = await self._find_support(claim, sources)
            verified_claims.append(
                {"claim": claim, "supported": support is not None, "source": support}
            )

        supported_count = sum(1 for c in verified_claims if c["supported"])
        accuracy = supported_count / max(len(verified_claims), 1)

        return {
            "accuracy": accuracy,
            "verified_claims": verified_claims,
            "total_claims": len(verified_claims),
            "supported_claims": supported_count,
        }

    def _extract_claims(self, answer: str) -> list[str]:
        """提取答案中的声明"""
        # 简化：按句子分割
        return self._split_sentences(answer)

    async def _find_support(self, claim: str, sources: list[dict]) -> str:
        """为声明查找支持"""
        # 简化：检查是否有源文档包含相似内容
        claim_lower = claim.lower()
        for source in sources:
            content = source.get("content", "").lower()
            # 简单的包含检查（实际应使用语义相似度）
            if any(word in content for word in claim_lower.split()[:5]):
                return source.get("document_id")
        return None
