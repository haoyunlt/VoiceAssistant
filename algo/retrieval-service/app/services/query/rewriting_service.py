"""
Query Rewriting Service - 查询重写服务

功能:
- 口语化转标准化
- 模板重写
- LLM重写（可选）
- 多候选生成

目标:
- 提升错误query准确率≥20%
- 重写延迟≤50ms (非LLM模式)
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

from app.observability.logging import logger


@dataclass
class RewriteResult:
    """重写结果"""

    original_query: str
    rewritten_queries: List[str]
    method: str  # template, llm, hybrid
    confidence: float
    latency_ms: float


class QueryRewritingService:
    """查询重写服务"""

    def __init__(
        self,
        templates_path: str = "data/rewrite_templates.json",
        llm_endpoint: Optional[str] = None,
        llm_model: str = "qwen-1.8b-chat",
        enable_llm: bool = False,
        llm_timeout: float = 3.0,
    ):
        """
        初始化查询重写服务

        Args:
            templates_path: 重写模板路径
            llm_endpoint: LLM API端点（可选）
            llm_model: LLM模型名称
            enable_llm: 是否启用LLM重写
            llm_timeout: LLM超时时间
        """
        self.templates_path = templates_path
        self.llm_endpoint = llm_endpoint
        self.llm_model = llm_model
        self.enable_llm = enable_llm
        self.llm_timeout = llm_timeout

        # 加载重写模板
        self.templates = self._load_templates()

        logger.info(
            f"Query rewriting service initialized: "
            f"templates={len(self.templates)}, llm_enabled={enable_llm}"
        )

    def _load_templates(self) -> List[dict]:
        """加载重写模板"""
        try:
            templates_file = Path(self.templates_path)
            if templates_file.exists():
                with open(templates_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("patterns", [])
            else:
                # 返回默认模板
                return self._default_templates()

        except Exception as e:
            logger.warning(f"Failed to load templates: {e}, using defaults")
            return self._default_templates()

    def _default_templates(self) -> List[dict]:
        """默认重写模板"""
        return [
            {
                "pattern": r"怎么(.+)",
                "template": "如何{matched}",
                "priority": 1,
            },
            {
                "pattern": r"咋样(.+)",
                "template": "{matched}怎么样",
                "priority": 1,
            },
            {
                "pattern": r"(.+)是啥",
                "template": "什么是{matched}",
                "priority": 1,
            },
            {
                "pattern": r"(.+)咋用",
                "template": "如何使用{matched}",
                "priority": 1,
            },
            {
                "pattern": r"为啥(.+)",
                "template": "为什么{matched}",
                "priority": 1,
            },
            {
                "pattern": r"(.+)和(.+)有什么区别",
                "template": "{matched1}与{matched2}的区别",
                "priority": 2,
            },
            {
                "pattern": r"(.+)好不好",
                "template": "{matched}的优缺点",
                "priority": 1,
            },
        ]

    async def rewrite(
        self, query: str, max_candidates: int = 3
    ) -> RewriteResult:
        """
        重写查询

        Args:
            query: 原始查询
            max_candidates: 最大候选数

        Returns:
            重写结果
        """
        start_time = time.time()

        try:
            # 1. 模板重写
            template_rewrites = self._template_rewrite(query)

            # 2. LLM重写（如果启用）
            llm_rewrites = []
            method = "template"

            if self.enable_llm and self.llm_endpoint:
                try:
                    llm_rewrite = await self._llm_rewrite(query)
                    if llm_rewrite:
                        llm_rewrites.append(llm_rewrite)
                        method = "hybrid" if template_rewrites else "llm"
                except Exception as e:
                    logger.warning(f"LLM rewrite failed: {e}, using template only")

            # 3. 合并候选
            all_candidates = template_rewrites + llm_rewrites

            # 去重并限制数量
            unique_candidates = []
            seen = {query}
            for candidate in all_candidates:
                if candidate not in seen and len(unique_candidates) < max_candidates:
                    unique_candidates.append(candidate)
                    seen.add(candidate)

            # 如果没有候选，返回原查询
            if not unique_candidates:
                unique_candidates = [query]

            latency_ms = (time.time() - start_time) * 1000

            result = RewriteResult(
                original_query=query,
                rewritten_queries=unique_candidates,
                method=method,
                confidence=0.8 if template_rewrites or llm_rewrites else 0.0,
                latency_ms=latency_ms,
            )

            logger.info(
                f"Query rewritten: '{query}' -> {len(unique_candidates)} candidates "
                f"in {latency_ms:.1f}ms (method={method})"
            )

            return result

        except Exception as e:
            logger.error(f"Query rewriting failed: {e}", exc_info=True)
            return RewriteResult(
                original_query=query,
                rewritten_queries=[query],
                method="fallback",
                confidence=0.0,
                latency_ms=(time.time() - start_time) * 1000,
            )

    def _template_rewrite(self, query: str) -> List[str]:
        """
        使用模板重写

        Args:
            query: 原始查询

        Returns:
            重写候选列表
        """
        candidates = []

        for template in self.templates:
            pattern = template["pattern"]
            template_str = template["template"]

            # 匹配模式
            match = re.match(pattern, query)
            if match:
                # 提取匹配组
                groups = match.groups()

                # 应用模板
                if len(groups) == 1:
                    rewritten = template_str.replace("{matched}", groups[0])
                    candidates.append(rewritten)
                elif len(groups) == 2:
                    rewritten = (
                        template_str.replace("{matched1}", groups[0])
                        .replace("{matched2}", groups[1])
                    )
                    candidates.append(rewritten)

        return candidates

    async def _llm_rewrite(self, query: str) -> Optional[str]:
        """
        使用LLM重写

        Args:
            query: 原始查询

        Returns:
            重写后的查询
        """
        if not self.llm_endpoint:
            return None

        try:
            prompt = self._build_rewrite_prompt(query)

            async with httpx.AsyncClient(timeout=self.llm_timeout) as client:
                response = await client.post(
                    f"{self.llm_endpoint}/api/v1/chat/completions",
                    json={
                        "model": self.llm_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 100,
                    },
                )
                response.raise_for_status()
                result = response.json()

            rewritten = result["choices"][0]["message"]["content"].strip()
            return rewritten

        except Exception as e:
            logger.warning(f"LLM rewrite request failed: {e}")
            return None

    def _build_rewrite_prompt(self, query: str) -> str:
        """构建LLM重写提示"""
        prompt = f"""请将以下口语化查询改写为标准化搜索查询。

要求:
1. 保持语义不变
2. 使用标准化、正式的表达
3. 去除冗余词汇
4. 只输出改写结果，不要解释

原查询: {query}

改写查询:"""

        return prompt

    async def batch_rewrite(
        self, queries: List[str], max_candidates: int = 3
    ) -> List[RewriteResult]:
        """
        批量重写

        Args:
            queries: 查询列表
            max_candidates: 最大候选数

        Returns:
            重写结果列表
        """
        tasks = [self.rewrite(q, max_candidates) for q in queries]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "templates_count": len(self.templates),
            "llm_enabled": self.enable_llm,
            "llm_endpoint": self.llm_endpoint,
            "llm_model": self.llm_model,
        }


# 使用示例
if __name__ == "__main__":

    async def test():
        service = QueryRewritingService(enable_llm=False)

        # 测试查询
        test_queries = [
            "Python怎么用",
            "机器学习是啥",
            "Docker咋样",
            "Python和Java有什么区别",
            "Kubernetes好不好",
        ]

        for query in test_queries:
            result = await service.rewrite(query)
            print(f"\n原查询: {result.original_query}")
            print(f"重写结果: {result.rewritten_queries}")
            print(f"方法: {result.method}")
            print(f"延迟: {result.latency_ms:.1f}ms")

    asyncio.run(test())
