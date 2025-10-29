"""
Query Classifier - 查询分类器

分析查询类型和复杂度，用于自适应路由
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryClassifier:
    """查询分类器"""

    def __init__(self, llm_client):
        """
        初始化查询分类器

        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
        logger.info("Query classifier initialized")

    async def classify(self, query: str) -> dict[str, Any]:
        """
        分类查询

        Args:
            query: 查询文本

        Returns:
            分类结果
        """
        # 使用 LLM 分析查询
        analysis = await self._analyze_with_llm(query)

        # 补充规则分析
        analysis.update(self._analyze_with_rules(query))

        logger.info(f"Query classified: type={analysis.get('type')}, complexity={analysis.get('complexity')}")
        return analysis

    async def _analyze_with_llm(self, query: str) -> dict[str, Any]:
        """使用 LLM 分析查询"""
        prompt = f"""分析以下查询并分类。

查询: {query}

请以 JSON 格式返回分析结果:
{{
    "type": "simple_fact|complex_reasoning|multi_hop|comparison|aggregation|open_ended|temporal|causal|hypothetical|procedural",
    "complexity": 1-10,
    "requires_multiple_sources": true/false,
    "temporal_aspect": true/false,
    "requires_calculation": true/false,
    "key_concepts": ["概念1", "概念2", ...],
    "reasoning": "简要说明"
}}

JSON:"""

        try:
            response = await self.llm_client.generate(
                prompt=prompt, temperature=0.3, max_tokens=400
            )

            # 提取 JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            analysis = json.loads(response)
            return analysis

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            # 返回默认分析
            return {
                "type": "simple_fact",
                "complexity": 5,
                "requires_multiple_sources": False,
                "temporal_aspect": False,
                "requires_calculation": False,
                "key_concepts": [],
                "reasoning": "Failed to analyze with LLM",
            }

    def _analyze_with_rules(self, query: str) -> dict[str, Any]:
        """使用规则分析查询（补充）"""
        query_lower = query.lower()

        analysis = {"rule_based": True}

        # 检测比较类查询
        comparison_words = ["compare", "difference", "versus", "vs", "比较", "对比", "区别"]
        if any(word in query_lower for word in comparison_words):
            analysis["has_comparison"] = True

        # 检测时间相关
        temporal_words = ["when", "date", "year", "time", "什么时候", "何时", "时间"]
        if any(word in query_lower for word in temporal_words):
            analysis["has_temporal"] = True

        # 检测数量相关
        quantity_words = ["how many", "count", "number", "多少", "数量"]
        if any(word in query_lower for word in quantity_words):
            analysis["has_quantity"] = True

        # 检测因果关系
        causal_words = ["why", "because", "cause", "reason", "为什么", "原因"]
        if any(word in query_lower for word in causal_words):
            analysis["has_causal"] = True

        # 估算查询长度复杂度
        word_count = len(query.split())
        if word_count > 20:
            analysis["length_complexity"] = "high"
        elif word_count > 10:
            analysis["length_complexity"] = "medium"
        else:
            analysis["length_complexity"] = "low"

        return analysis

