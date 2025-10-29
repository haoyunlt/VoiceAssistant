"""
HyDE (Hypothetical Document Embeddings) Service

核心思想:
- 用户查询可能不完整或不精确
- 生成一个"假设性答案"（hypothetical document）
- 使用答案的embedding进行检索（而不是查询的embedding）
- 假设性答案通常包含更多上下文，检索效果更好

优势:
- 知识密集型查询准确率提升≥25%
- 适合开放式问题
- 减少query-document语义差距

适用场景:
- "什么是量子计算？"
- "如何实现分布式锁？"
- "解释一下XXX原理"
"""

import asyncio
import time
from dataclasses import dataclass

import httpx

from app.observability.logging import logger


@dataclass
class HyDEResult:
    """HyDE生成结果"""

    original_query: str
    hypothetical_document: str
    method: str  # llm, template
    latency_ms: float = 0.0
    token_count: int = 0


class HyDEService:
    """HyDE服务"""

    def __init__(
        self,
        llm_endpoint: str | None = None,
        llm_model: str = "qwen-7b",
        temperature: float = 0.3,
        max_tokens: int = 200,
        timeout: float = 5.0,
    ):
        """
        初始化HyDE服务

        Args:
            llm_endpoint: LLM API endpoint
            llm_model: LLM模型名称
            temperature: LLM温度（较低温度保证答案质量）
            max_tokens: 假设性文档的最大token数
            timeout: 超时时间
        """
        self.llm_endpoint = llm_endpoint
        self.llm_model = llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        logger.info(
            f"HyDE service initialized: model={llm_model}, "
            f"temperature={temperature}, max_tokens={max_tokens}"
        )

    async def generate(self, query: str) -> HyDEResult:
        """
        为查询生成假设性文档

        Args:
            query: 用户查询

        Returns:
            HyDE生成结果
        """
        start_time = time.time()

        if not self.llm_endpoint:
            logger.warning("No LLM endpoint, using template fallback")
            doc = self._generate_with_template(query)
            method = "template"
            token_count = 0
        else:
            try:
                doc, token_count = await self._generate_with_llm(query)
                method = "llm"
            except Exception as e:
                logger.error(f"HyDE LLM generation failed: {e}, fallback to template")
                doc = self._generate_with_template(query)
                method = "template_fallback"
                token_count = 0

        latency_ms = (time.time() - start_time) * 1000

        result = HyDEResult(
            original_query=query,
            hypothetical_document=doc,
            method=method,
            latency_ms=latency_ms,
            token_count=token_count,
        )

        logger.info(
            f"HyDE generated ({method}): {len(doc)} chars, "
            f"{latency_ms:.1f}ms, {token_count} tokens"
        )

        return result

    async def _generate_with_llm(self, query: str) -> tuple[str, int]:
        """
        使用LLM生成假设性文档

        Args:
            query: 用户查询

        Returns:
            (假设性文档, token数)
        """
        prompt = self._build_prompt(query)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.llm_endpoint}/api/v1/chat/completions",
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            )
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"].strip()
        token_count = result.get("usage", {}).get("total_tokens", 0)

        return content, token_count

    def _build_prompt(self, query: str) -> str:
        """
        构建HyDE提示词

        Args:
            query: 用户查询

        Returns:
            提示词
        """
        # 核心策略：让LLM生成一个可能回答该问题的文档片段
        prompt = f"""请基于以下问题，生成一个可能回答该问题的文档片段（100-150字）。

问题：{query}

要求：
1. 生成的内容应该像一个知识库文档的片段
2. 包含可能回答该问题的关键信息
3. 使用正式的、说明性的语言
4. 不要包含"根据问题"等元信息
5. 直接给出文档内容，不需要前缀

文档片段："""

        return prompt

    def _generate_with_template(self, query: str) -> str:
        """
        使用模板生成简单的假设性文档（备用方案）

        Args:
            query: 用户查询

        Returns:
            假设性文档
        """
        # 简单的模板生成：将问题转换为陈述
        templates = [
            f"关于{query}的说明：这是一个常见问题，涉及多个方面的知识点。",
            f"{query}的详细解释包括其定义、应用场景和相关注意事项。",
            f"理解{query}需要掌握相关的基础概念和实践经验。",
        ]

        # 选择最匹配的模板
        if query.startswith(("什么", "啥")):
            doc = f"{query}是指相关领域的一个重要概念，具有特定的含义和应用场景。"
        elif query.startswith(("如何", "怎么", "怎样")):
            doc = f"实现{query}的方法包括多个步骤，需要按照正确的流程进行操作。"
        elif query.startswith(("为什么", "为何")):
            doc = f"{query}的原因涉及多个因素，包括技术、业务和实际应用的考虑。"
        else:
            doc = templates[0]

        return doc

    async def generate_batch(self, queries: list[str]) -> list[HyDEResult]:
        """
        批量生成假设性文档

        Args:
            queries: 查询列表

        Returns:
            HyDE结果列表
        """
        tasks = [self.generate(query) for query in queries]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "llm_endpoint": self.llm_endpoint,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "llm_available": self.llm_endpoint is not None,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = HyDEService(
            llm_endpoint=None,  # 使用模板fallback
        )

        queries = [
            "什么是量子计算？",
            "如何实现分布式锁？",
            "为什么需要使用Redis？",
        ]

        for query in queries:
            result = await service.generate(query)
            print(f"\n查询: {result.original_query}")
            print(f"假设文档: {result.hypothetical_document}")
            print(f"方法: {result.method}")
            print(f"延迟: {result.latency_ms:.1f}ms")

    asyncio.run(test())
