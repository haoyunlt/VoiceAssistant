"""
降级策略 - Fallback Strategy

当服务不可用或失败时的降级方案。

降级链路：
1. 优先: 语义缓存
2. 次选: Embedding 缓存 + 模板答案
3. 再次: 返回候选文档（不生成答案）
4. 最后: 错误提示 + 日志告警
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """降级策略"""

    def __init__(self, cache_service=None):
        """
        初始化降级策略

        Args:
            cache_service: 缓存服务
        """
        self.cache_service = cache_service

    async def handle_llm_failure(
        self, query: str, documents: list[dict], error: Exception
    ) -> dict[str, Any]:
        """
        处理 LLM 失败

        Args:
            query: 查询
            documents: 检索到的文档
            error: 错误

        Returns:
            降级响应
        """
        logger.error(f"LLM failure, applying fallback: {error}")

        # 策略 1: 尝试从缓存获取
        if self.cache_service:
            try:
                cached = await self.cache_service.get_cached_answer(query)
                if cached:
                    logger.info("Fallback: using cached answer")
                    return {
                        "answer": cached.get("answer", ""),
                        "sources": cached.get("sources", []),
                        "fallback": "cache",
                        "error": str(error),
                    }
            except Exception as e:
                logger.warning(f"Cache fallback failed: {e}")

        # 策略 2: 返回文档摘要（模板答案）
        if documents:
            logger.info("Fallback: returning document summary")
            summary = self._generate_template_answer(query, documents)
            return {
                "answer": summary,
                "documents": documents[:3],
                "sources": [
                    {"id": doc.get("id"), "score": doc.get("score")} for doc in documents[:3]
                ],
                "fallback": "document_summary",
                "error": str(error),
            }

        # 策略 3: 错误提示
        logger.error("Fallback: no documents available, returning error message")
        return {
            "answer": "抱歉，服务暂时不可用，请稍后再试。",
            "documents": [],
            "sources": [],
            "fallback": "error_message",
            "error": str(error),
        }

    def _generate_template_answer(self, query: str, documents: list[dict]) -> str:
        """生成模板答案"""
        if not documents:
            return "抱歉，未找到相关信息。"

        # 简单的模板拼接
        parts = [f"关于「{query}」，找到以下相关信息：\n"]

        for i, doc in enumerate(documents[:3], 1):
            content = doc.get("content", "")[:200]  # 截断
            parts.append(f"{i}. {content}...")

        parts.append("\n\n（注：由于服务繁忙，返回的是文档摘要，如需详细解答请稍后再试）")

        return "\n\n".join(parts)

    async def handle_retrieval_failure(self, query: str, error: Exception) -> dict[str, Any]:
        """
        处理检索失败

        Args:
            query: 查询
            error: 错误

        Returns:
            降级响应
        """
        logger.error(f"Retrieval failure, applying fallback: {error}")

        # 策略 1: 尝试从缓存获取完整答案
        if self.cache_service:
            try:
                cached = await self.cache_service.get_cached_answer(query)
                if cached:
                    logger.info("Fallback: using cached complete answer")
                    return {
                        "answer": cached.get("answer", ""),
                        "sources": cached.get("sources", []),
                        "fallback": "cache_complete",
                        "error": str(error),
                    }
            except Exception as e:
                logger.warning(f"Cache fallback failed: {e}")

        # 策略 2: 返回错误提示
        return {
            "answer": "抱歉，检索服务暂时不可用，请稍后再试。",
            "documents": [],
            "sources": [],
            "fallback": "retrieval_error",
            "error": str(error),
        }

    async def handle_cache_failure(self, _query: str, documents: list[dict]) -> dict[str, Any]:
        """
        处理缓存失败（降级到直接检索）

        Args:
            query: 查询
            documents: 文档

        Returns:
            正常流程继续
        """
        logger.warning("Cache unavailable, skipping cache")
        return {
            "documents": documents,
            "fallback": "skip_cache",
        }

    async def handle_rerank_failure(self, documents: list[dict]) -> list[dict]:
        """
        处理重排失败（降级到原始排序）

        Args:
            documents: 文档

        Returns:
            原始文档
        """
        logger.warning("Reranking unavailable, using original ranking")
        return documents


# 全局实例
_fallback_strategy: FallbackStrategy | None = None


def get_fallback_strategy(cache_service=None) -> FallbackStrategy:
    """获取降级策略实例"""
    global _fallback_strategy
    if _fallback_strategy is None:
        _fallback_strategy = FallbackStrategy(cache_service)
    return _fallback_strategy
