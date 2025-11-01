"""
Multi-Query Generation Service - 多查询生成服务

功能:
- 从单个查询生成多个变体查询
- 使用LLM生成语义相似但表达不同的查询
- 提高复杂查询的召回率和准确性

优势:
- 覆盖不同的查询角度
- 提升复杂问题的准确率（目标≥20%）
- 适合开放式问题和多意图查询
"""

import asyncio
import re
import time
from dataclasses import dataclass

import httpx

from app.observability.logging import logger


@dataclass
class MultiQueryResult:
    """多查询生成结果"""

    original: str
    queries: list[str]  # 包含原查询
    method: str  # llm, template, hybrid
    latency_ms: float = 0.0


class MultiQueryService:
    """多查询生成服务"""

    def __init__(
        self,
        llm_endpoint: str | None = None,
        llm_model: str = "qwen-7b",
        num_queries: int = 3,
        temperature: float = 0.7,
        timeout: float = 5.0,
    ):
        """
        初始化多查询生成服务

        Args:
            llm_endpoint: LLM API endpoint
            llm_model: LLM模型名称
            num_queries: 生成的查询数量（不包含原查询）
            temperature: LLM温度（控制多样性）
            timeout: LLM调用超时（秒）
        """
        self.llm_endpoint = llm_endpoint
        self.llm_model = llm_model
        self.num_queries = num_queries
        self.temperature = temperature
        self.timeout = timeout

        logger.info(
            f"Multi-query service initialized: model={llm_model}, "
            f"num_queries={num_queries}, temperature={temperature}"
        )

    async def generate(self, query: str, num_queries: int | None = None) -> MultiQueryResult:
        """
        生成多个查询变体

        Args:
            query: 原始查询
            num_queries: 生成数量（覆盖默认值）

        Returns:
            多查询生成结果
        """
        start_time = time.time()
        num = num_queries or self.num_queries

        # 如果没有配置LLM endpoint，使用模板方法
        if not self.llm_endpoint:
            logger.warning("No LLM endpoint configured, using template-based generation")
            queries = self._generate_with_templates(query, num)
            method = "template"
        else:
            try:
                # 使用LLM生成
                queries = await self._generate_with_llm(query, num)
                method = "llm"
            except Exception as e:
                logger.error(f"LLM generation failed: {e}, fallback to template")
                queries = self._generate_with_templates(query, num)
                method = "template_fallback"

        # 始终包含原查询
        all_queries = [query] + queries

        latency_ms = (time.time() - start_time) * 1000

        result = MultiQueryResult(
            original=query,
            queries=all_queries,
            method=method,
            latency_ms=latency_ms,
        )

        logger.info(f"Generated {len(all_queries)} queries in {latency_ms:.1f}ms (method={method})")

        return result

    async def _generate_with_llm(self, query: str, num: int) -> list[str]:
        """
        使用LLM生成多个查询变体

        Args:
            query: 原始查询
            num: 生成数量

        Returns:
            生成的查询列表
        """
        # 构建提示词
        prompt = self._build_prompt(query, num)

        # 调用LLM
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.llm_endpoint}/api/v1/chat/completions",
                json={
                    "model": self.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            result = response.json()

        # 解析结果
        content = result["choices"][0]["message"]["content"]
        queries = self._parse_llm_response(content, query)

        return queries[:num]

    def _build_prompt(self, query: str, num: int) -> str:
        """
        构建LLM提示词

        Args:
            query: 原始查询
            num: 生成数量

        Returns:
            提示词
        """
        prompt = f"""请为以下查询生成{num}个不同的变体。这些变体应该：
1. 保持原始查询的核心意图
2. 使用不同的表达方式和词汇
3. 从不同角度提问
4. 保持查询的完整性

原始查询: {query}

要求:
- 每行一个查询变体
- 不要编号或添加前缀
- 不要重复原查询
- 保持自然流畅

查询变体:"""

        return prompt

    def _parse_llm_response(self, content: str, original_query: str) -> list[str]:
        """
        解析LLM响应

        Args:
            content: LLM返回的文本
            original_query: 原查询（用于去重）

        Returns:
            解析后的查询列表
        """
        queries = []
        lines = content.strip().split("\n")

        for line in lines:
            # 清理行
            line = line.strip()

            # 移除可能的编号
            line = re.sub(r"^\d+[.、)\s]+", "", line)

            # 移除引号
            line = line.strip('"\'""')  # noqa: B005

            # 检查有效性
            if line and len(line) > 3 and line != original_query:  # noqa: SIM102
                # 避免完全重复
                if line not in queries:
                    queries.append(line)

        return queries

    def _generate_with_templates(self, query: str, num: int) -> list[str]:
        """
        使用模板生成查询变体（备用方案）

        Args:
            query: 原始查询
            num: 生成数量

        Returns:
            生成的查询列表
        """
        templates = [
            lambda q: f"请问{q}",
            lambda q: f"我想了解{q}",
            lambda q: f"能否解释一下{q}",
            lambda q: f"关于{q}的问题",
            lambda q: f"{q}的详细信息",
            lambda q: f"帮我查一下{q}",
        ]

        queries = []
        for _i, template in enumerate(templates[:num]):
            try:
                variant = template(query)
                if variant != query:
                    queries.append(variant)
            except Exception as e:
                logger.warning(f"Template generation failed: {e}")

        return queries

    async def generate_batch(
        self, queries: list[str], num_queries: int | None = None
    ) -> list[MultiQueryResult]:
        """
        批量生成多查询

        Args:
            queries: 查询列表
            num_queries: 每个查询生成的数量

        Returns:
            生成结果列表
        """
        tasks = [self.generate(query, num_queries) for query in queries]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "llm_endpoint": self.llm_endpoint,
            "llm_model": self.llm_model,
            "num_queries": self.num_queries,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "llm_available": self.llm_endpoint is not None,
        }


# 简化版本：不依赖LLM的多查询生成器
class SimpleMultiQueryGenerator:
    """简单的多查询生成器（基于规则，无需LLM）"""

    def __init__(self, num_queries: int = 3):
        self.num_queries = num_queries

    async def generate(self, query: str) -> list[str]:
        """
        生成查询变体（基于规则）

        策略:
        1. 同义词替换（使用expansion_service的词典）
        2. 句式转换
        3. 问法变化
        """
        variants = [query]  # 始终包含原查询

        # 策略1: 添加疑问前缀
        if not any(query.startswith(prefix) for prefix in ["如何", "怎么", "什么", "为什么"]):
            variants.append(f"如何{query}")

        # 策略2: 问题转换
        question_transforms = {
            "如何": ["怎么", "怎样", "如何才能"],
            "怎么": ["如何", "怎样"],
            "什么": ["啥", "哪些"],
            "为什么": ["为何", "什么原因"],
        }

        for original, replacements in question_transforms.items():
            if query.startswith(original):
                for replacement in replacements[: self.num_queries]:
                    variant = query.replace(original, replacement, 1)
                    if variant not in variants:
                        variants.append(variant)

        return variants[: self.num_queries + 1]


# 使用示例
if __name__ == "__main__":

    async def test():
        # 测试LLM版本
        service = MultiQueryService(
            llm_endpoint="http://localhost:8000",
            num_queries=3,
        )

        result = await service.generate("如何使用Python进行数据分析")
        print(f"原查询: {result.original}")
        print(f"生成查询: {result.queries}")
        print(f"方法: {result.method}")
        print(f"延迟: {result.latency_ms}ms")

    asyncio.run(test())
