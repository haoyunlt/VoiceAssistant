"""
Self-RAG 完整服务 - 整合检索、生成、验证、修正

Self-RAG (Self-Reflective Retrieval Augmented Generation) 流程:
1. 检索评估: 评估检索结果质量
2. 自适应检索: 根据查询选择最优检索策略
3. 生成答案: 基于检索结果生成答案
4. 幻觉检测: 检测生成内容是否基于事实
5. 自我修正: 如有问题则重新检索或生成

实现了完整的 Iter 2 功能。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.self_rag.adaptive_retriever import AdaptiveRetriever, RetrievalStrategy
from app.core.self_rag.critique import RetrievalAssessment, RetrievalCritic
from app.core.self_rag.hallucination_detector import (
    HallucinationDetector,
    HallucinationLevel,
    HallucinationReport,
)

logger = logging.getLogger(__name__)


class SelfRAGMode(Enum):
    """Self-RAG 模式"""

    STANDARD = "standard"  # 标准模式：检索 → 生成
    ADAPTIVE = "adaptive"  # 自适应：动态选择策略
    STRICT = "strict"  # 严格模式：强制验证和修正
    FAST = "fast"  # 快速模式：跳过部分验证


@dataclass
class SelfRAGConfig:
    """Self-RAG 配置"""

    mode: SelfRAGMode = SelfRAGMode.ADAPTIVE
    max_refinement_attempts: int = 2
    hallucination_threshold: float = 0.3
    enable_retrieval_critique: bool = True
    enable_hallucination_detection: bool = True
    enable_query_rewrite: bool = True
    enable_citations: bool = True


@dataclass
class SelfRAGResult:
    """Self-RAG 执行结果"""

    query: str
    answer: str
    confidence: float
    retrieval_strategy: str
    retrieval_assessment: RetrievalAssessment | None
    hallucination_report: HallucinationReport | None
    refinement_count: int
    citations: list[dict[str, str]]
    metadata: dict[str, Any]


class SelfRAGService:
    """
    Self-RAG 完整服务

    用法:
        service = SelfRAGService(
            llm_client=llm_client,
            knowledge_base=kb_client,
            cache=redis_client
        )

        # 执行 Self-RAG
        result = await service.query(
            query="What is Python?",
            config=SelfRAGConfig(mode=SelfRAGMode.STRICT)
        )

        print(f"Answer: {result.answer}")
        print(f"Confidence: {result.confidence}")
        print(f"Hallucination: {result.hallucination_report.level}")
    """

    def __init__(
        self,
        llm_client: Any,
        knowledge_base: Any,
        cache: Any | None = None,
        default_config: SelfRAGConfig | None = None,
    ):
        """
        初始化 Self-RAG 服务

        Args:
            llm_client: LLM 客户端
            knowledge_base: 知识库客户端
            cache: 缓存客户端（Redis）
            default_config: 默认配置
        """
        self.llm_client = llm_client
        self.knowledge_base = knowledge_base
        self.cache = cache
        self.default_config = default_config or SelfRAGConfig()

        # 初始化子模块
        self.adaptive_retriever = AdaptiveRetriever(
            knowledge_base=knowledge_base,
            cache=cache,
            llm_client=llm_client,
            enable_cache=True,
        )

        self.retrieval_critic = RetrievalCritic(
            llm_client=llm_client, model="gpt-3.5-turbo"
        )

        self.hallucination_detector = HallucinationDetector(
            llm_client=llm_client,
            model="gpt-4",
            enable_citations=True,
        )

        # 统计信息
        self.stats = {
            "total_queries": 0,
            "refinement_triggered": 0,
            "hallucination_detected": 0,
            "query_rewrites": 0,
        }

        logger.info("SelfRAGService initialized with Iter 2 complete implementation")

    async def query(
        self,
        query: str,
        context: dict | None = None,
        config: SelfRAGConfig | None = None,
    ) -> SelfRAGResult:
        """
        执行 Self-RAG 查询

        Args:
            query: 用户查询
            context: 上下文信息
            config: Self-RAG 配置

        Returns:
            Self-RAG 执行结果
        """
        self.stats["total_queries"] += 1
        config = config or self.default_config

        logger.info(f"Self-RAG query: {query[:50]}... (mode={config.mode.value})")

        # 1. 自适应检索
        retrieval_result = await self.adaptive_retriever.retrieve(query, context)
        documents = retrieval_result["documents"]
        strategy = retrieval_result["strategy"]

        # 2. 评估检索质量（如果启用）
        retrieval_assessment = None
        if config.enable_retrieval_critique and documents:
            retrieval_assessment = await self.retrieval_critic.assess_relevance(
                query, documents, use_llm=(config.mode != SelfRAGMode.FAST)
            )

            # 如果检索质量不佳，尝试重写查询
            if (
                config.enable_query_rewrite
                and retrieval_assessment.need_rewrite
                and retrieval_assessment.suggested_rewrite
            ):
                logger.info(f"Rewriting query: {retrieval_assessment.suggested_rewrite}")
                self.stats["query_rewrites"] += 1

                # 使用重写后的查询再次检索
                retrieval_result = await self.adaptive_retriever.retrieve(
                    retrieval_assessment.suggested_rewrite, context
                )
                documents = retrieval_result["documents"]

        # 3. 生成答案
        answer = await self._generate_answer(query, documents, context)

        # 4. 幻觉检测与修正（如果启用）
        hallucination_report = None
        refinement_count = 0

        if config.enable_hallucination_detection and documents:
            # 快速模式跳过验证
            if config.mode == SelfRAGMode.FAST:
                logger.debug("Fast mode: skipping hallucination detection")
            else:
                answer, hallucination_report, refinement_count = (
                    await self._verify_and_refine(
                        query,
                        answer,
                        documents,
                        max_attempts=config.max_refinement_attempts,
                        hallucination_threshold=config.hallucination_threshold,
                    )
                )

        # 5. 添加引用（如果启用）
        citations = []
        if config.enable_citations and hallucination_report:
            answer = await self.hallucination_detector.add_citations(
                answer, hallucination_report
            )
            citations = hallucination_report.citations

        # 6. 计算置信度
        confidence = self._calculate_confidence(
            retrieval_assessment, hallucination_report, refinement_count
        )

        # 7. 构建结果
        result = SelfRAGResult(
            query=query,
            answer=answer,
            confidence=confidence,
            retrieval_strategy=strategy,
            retrieval_assessment=retrieval_assessment,
            hallucination_report=hallucination_report,
            refinement_count=refinement_count,
            citations=citations,
            metadata={
                "mode": config.mode.value,
                "documents_retrieved": len(documents),
                "query_rewritten": retrieval_assessment.need_rewrite
                if retrieval_assessment
                else False,
            },
        )

        logger.info(
            f"Self-RAG completed: confidence={confidence:.2f}, "
            f"refinements={refinement_count}"
        )

        return result

    async def _generate_answer(
        self, query: str, documents: list[str], context: dict | None
    ) -> str:
        """生成答案"""
        if not documents:
            # 无检索结果，直接使用 LLM
            prompt = f"请回答以下问题: {query}"
        else:
            # 基于检索结果生成
            docs_text = "\n\n".join([f"文档{i+1}:\n{doc}" for i, doc in enumerate(documents)])
            prompt = f"""基于以下文档回答问题。如果文档中没有相关信息，请明确说明。

问题: {query}

参考文档:
{docs_text}

请给出准确、有根据的答案:"""

        try:
            response = await self.llm_client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个准确、有根据的AI助手。所有回答必须基于提供的文档。",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4",
                temperature=0.3,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return "抱歉，生成答案时出错。"

    async def _verify_and_refine(
        self,
        query: str,
        answer: str,
        documents: list[str],
        max_attempts: int = 2,
        hallucination_threshold: float = 0.3,
    ) -> tuple[str, HallucinationReport, int]:
        """
        验证并修正答案

        Returns:
            (最终答案, 幻觉报告, 修正次数)
        """
        refinement_count = 0
        current_answer = answer
        final_report = None

        for attempt in range(max_attempts):
            # 检测幻觉
            report = await self.hallucination_detector.detect(
                current_answer, documents, query
            )

            final_report = report

            # 如果幻觉水平可接受，退出
            if report.level in [HallucinationLevel.NONE, HallucinationLevel.LOW]:
                logger.info(f"Answer verified: hallucination level = {report.level.value}")
                break

            # 如果检测到严重幻觉，尝试修正
            if report.level in [HallucinationLevel.MEDIUM, HallucinationLevel.HIGH]:
                logger.warning(
                    f"Hallucination detected (level={report.level.value}), "
                    f"attempting refinement {attempt + 1}/{max_attempts}"
                )

                self.stats["hallucination_detected"] += 1
                self.stats["refinement_triggered"] += 1
                refinement_count += 1

                # 生成修正建议
                corrected_answer = await self.hallucination_detector._suggest_correction(
                    current_answer, documents, report
                )

                current_answer = corrected_answer
            else:
                break

        return current_answer, final_report, refinement_count

    def _calculate_confidence(
        self,
        retrieval_assessment: RetrievalAssessment | None,
        hallucination_report: HallucinationReport | None,
        refinement_count: int,
    ) -> float:
        """
        计算整体置信度

        综合考虑:
        - 检索质量（相关性、充分性）
        - 幻觉检测结果
        - 修正次数
        """
        confidence = 1.0

        # 检索质量影响
        if retrieval_assessment:
            if not retrieval_assessment.is_sufficient:
                confidence *= 0.7
            confidence *= retrieval_assessment.confidence

        # 幻觉影响
        if hallucination_report:
            if hallucination_report.level == HallucinationLevel.NONE:
                confidence *= 1.0
            elif hallucination_report.level == HallucinationLevel.LOW:
                confidence *= 0.9
            elif hallucination_report.level == HallucinationLevel.MEDIUM:
                confidence *= 0.7
            else:  # HIGH
                confidence *= 0.4

            confidence *= hallucination_report.confidence

        # 修正次数影响（每次修正降低 10% 置信度）
        confidence *= 0.9**refinement_count

        return max(0.0, min(1.0, confidence))

    def get_stats(self) -> dict:
        """获取统计信息"""
        refinement_rate = (
            self.stats["refinement_triggered"] / self.stats["total_queries"]
            if self.stats["total_queries"] > 0
            else 0.0
        )

        hallucination_rate = (
            self.stats["hallucination_detected"] / self.stats["total_queries"]
            if self.stats["total_queries"] > 0
            else 0.0
        )

        return {
            **self.stats,
            "refinement_rate": refinement_rate,
            "hallucination_rate": hallucination_rate,
            "retriever_stats": self.adaptive_retriever.get_stats(),
        }

    async def batch_query(
        self, queries: list[str], config: SelfRAGConfig | None = None
    ) -> list[SelfRAGResult]:
        """
        批量查询

        Args:
            queries: 查询列表
            config: Self-RAG 配置

        Returns:
            结果列表
        """
        import asyncio

        tasks = [self.query(query, config=config) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Query {i} failed: {result}")
                final_results.append(
                    SelfRAGResult(
                        query=queries[i],
                        answer=f"Error: {str(result)}",
                        confidence=0.0,
                        retrieval_strategy="error",
                        retrieval_assessment=None,
                        hallucination_report=None,
                        refinement_count=0,
                        citations=[],
                        metadata={"error": str(result)},
                    )
                )
            else:
                final_results.append(result)

        return final_results


# 便捷函数
async def create_self_rag_service(
    llm_client: Any,
    knowledge_base: Any,
    cache: Any | None = None,
    mode: SelfRAGMode = SelfRAGMode.ADAPTIVE,
) -> SelfRAGService:
    """
    创建 Self-RAG 服务的便捷函数

    Args:
        llm_client: LLM 客户端
        knowledge_base: 知识库客户端
        cache: 缓存客户端
        mode: 默认模式

    Returns:
        Self-RAG 服务实例
    """
    config = SelfRAGConfig(mode=mode)
    service = SelfRAGService(
        llm_client=llm_client,
        knowledge_base=knowledge_base,
        cache=cache,
        default_config=config,
    )

    logger.info(f"Self-RAG service created (mode={mode.value})")
    return service

