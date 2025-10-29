"""
Self-RAG Service - 自我纠错服务

实现两阶段生成：Generate → Verify → Refine
"""

import logging
from typing import Any

from app.observability.metrics import record_hallucination_detected
from app.self_rag.hallucination_detector import HallucinationDetector

logger = logging.getLogger(__name__)


class SelfRAGService:
    """Self-RAG 服务"""

    def __init__(
        self,
        llm_client,
        hallucination_detector: HallucinationDetector,
        max_refinement_attempts: int = 2,
        hallucination_threshold: float = 0.7,
    ):
        """
        初始化 Self-RAG 服务

        Args:
            llm_client: LLM 客户端
            hallucination_detector: 幻觉检测器
            max_refinement_attempts: 最大修正次数
            hallucination_threshold: 幻觉检测阈值
        """
        self.llm_client = llm_client
        self.hallucination_detector = hallucination_detector
        self.max_refinement_attempts = max_refinement_attempts
        self.hallucination_threshold = hallucination_threshold

        logger.info(f"Self-RAG service initialized (max_attempts={max_refinement_attempts})")

    async def generate_with_self_check(
        self,
        query: str,
        context: str,
        temperature: float = 0.7,
        tenant_id: str = "default",
    ) -> dict[str, Any]:
        """
        生成答案并进行自我检查

        Args:
            query: 查询
            context: 上下文
            temperature: LLM 温度
            tenant_id: 租户 ID

        Returns:
            生成结果
        """
        attempts = []
        final_answer = None
        has_hallucination = False

        for attempt in range(self.max_refinement_attempts + 1):
            logger.info(f"Generation attempt {attempt + 1}/{self.max_refinement_attempts + 1}")

            # 1. 生成答案
            if attempt == 0:
                # 首次生成
                answer = await self._generate_initial_answer(query, context, temperature)
            else:
                # 修正生成
                answer = await self._refine_answer(query, context, attempts[-1], temperature)

            # 2. 检测幻觉
            detection_result = await self.hallucination_detector.detect(
                answer=answer,
                context=context,
                query=query,
                threshold=self.hallucination_threshold,
            )

            # 记录本次尝试
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "answer": answer,
                    "detection": detection_result,
                }
            )

            has_hallucination = detection_result.get("has_hallucination", False)
            confidence = detection_result.get("confidence", 0.5)

            logger.info(
                f"Attempt {attempt + 1}: hallucination={has_hallucination}, confidence={confidence:.2f}"
            )

            # 3. 判断是否需要继续修正
            if not has_hallucination or confidence < self.hallucination_threshold:
                # 没有幻觉或置信度低，接受答案
                final_answer = answer
                logger.info(f"Answer accepted at attempt {attempt + 1}")
                break

            # 记录幻觉
            record_hallucination_detected(tenant_id=tenant_id)

            if attempt >= self.max_refinement_attempts:
                # 达到最大尝试次数
                final_answer = answer
                logger.warning(
                    "Max refinement attempts reached, using last answer (may contain hallucination)"
                )
                break

        return {
            "answer": final_answer,
            "has_hallucination": has_hallucination,
            "confidence": attempts[-1]["detection"].get("confidence", 0.5),
            "attempts": len(attempts),
            "detection_history": attempts,
            "final_detection": attempts[-1]["detection"],
        }

    async def _generate_initial_answer(self, query: str, context: str, temperature: float) -> str:
        """生成初始答案"""
        prompt = f"""基于以下上下文回答问题。请确保答案完全基于上下文，不要添加上下文中没有的信息。

上下文:
{context}

问题: {query}

答案:"""

        answer = await self.llm_client.generate(
            prompt=prompt, temperature=temperature, max_tokens=500
        )
        return answer.strip()

    async def _refine_answer(
        self,
        query: str,
        context: str,
        previous_attempt: dict[str, Any],
        temperature: float,
    ) -> str:
        """修正答案"""
        previous_answer = previous_attempt["answer"]
        detection = previous_attempt["detection"]
        reasons = detection.get("reasons", [])

        reasons_text = "\n".join([f"- {r}" for r in reasons])

        prompt = f"""之前的答案被检测到可能存在幻觉或不准确的内容。请重新生成答案。

上下文:
{context}

问题: {query}

之前的答案:
{previous_answer}

检测到的问题:
{reasons_text}

要求:
1. 严格基于上下文回答
2. 避免添加上下文中没有的信息
3. 如果上下文不足以回答，明确说明
4. 对不确定的部分使用谨慎的措辞

修正后的答案:"""

        refined_answer = await self.llm_client.generate(
            prompt=prompt,
            temperature=temperature * 0.8,
            max_tokens=500,  # 降低温度以提高准确性
        )
        return refined_answer.strip()

    async def add_citations(self, answer: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """
        为答案添加引用

        Args:
            answer: 答案
            documents: 源文档

        Returns:
            带引用的答案
        """
        # 为每个文档编号
        doc_map = dict(enumerate(documents))

        # 使用 LLM 标注引用
        doc_list = "\n\n".join(
            [f"[{i}] {doc.get('content', '')[:200]}..." for i, doc in doc_map.items()]
        )

        prompt = f"""为答案中的每个事实性陈述添加引用编号 [N]。

文档:
{doc_list}

答案:
{answer}

请在答案中适当位置插入 [N] 引用标记，N 是文档编号。

带引用的答案:"""

        try:
            cited_answer = await self.llm_client.generate(
                prompt=prompt, temperature=0.3, max_tokens=600
            )

            return {
                "answer_with_citations": cited_answer.strip(),
                "citations": doc_map,
            }
        except Exception as e:
            logger.error(f"Failed to add citations: {e}")
            return {"answer_with_citations": answer, "citations": doc_map}

    async def estimate_confidence(self, answer: str, context: str, query: str) -> float:
        """
        估算答案的置信度

        Args:
            answer: 答案
            context: 上下文
            query: 查询

        Returns:
            置信度 (0-1)
        """
        prompt = f"""评估以下答案的可靠性和置信度。

查询: {query}
上下文: {context[:500]}
答案: {answer}

请以 0-1 的分数评估置信度，其中:
- 1.0: 完全支持，非常可靠
- 0.5: 部分支持，有些不确定
- 0.0: 不支持，不可靠

仅返回数字分数:"""

        try:
            response = await self.llm_client.generate(prompt=prompt, temperature=0.2, max_tokens=10)
            # 提取数字
            import re

            match = re.search(r"0?\.\d+|[01]\.0?", response)
            if match:
                confidence = float(match.group())
                return max(0.0, min(1.0, confidence))
        except Exception as e:
            logger.error(f"Confidence estimation failed: {e}")

        return 0.5  # 默认中等置信度
