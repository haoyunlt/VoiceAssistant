"""
智能模型路由 - Model Selector

根据查询复杂度和租户等级，智能选择最优模型，平衡成本与质量。

成本对比（每 1K tokens）:
- gpt-4-turbo:      $0.01 (input) / $0.03 (output)
- gpt-3.5-turbo:    $0.0005 (input) / $0.0015 (output)  (成本 1/20)
- claude-3-haiku:   $0.00025 (input) / $0.00125 (output) (成本 1/40)

策略：
- 简单查询 (复杂度 <5) → gpt-3.5-turbo (节省 95%)
- 中等查询 (5-8) → gpt-4-turbo
- 复杂查询 (>8) → gpt-4-turbo + self-rag
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# 模型定义
ModelType = Literal["gpt-4-turbo", "gpt-3.5-turbo", "claude-3-haiku"]

# 租户等级
TierType = Literal["free", "standard", "premium", "enterprise"]


class QueryComplexityClassifier:
    """查询复杂度分类器"""

    def __init__(self):
        """初始化分类器"""
        # 复杂度特征权重
        self.features = {
            "length": 0.2,  # 查询长度
            "multi_part": 0.3,  # 多部分查询
            "reasoning": 0.3,  # 推理词汇
            "calculation": 0.2,  # 计算需求
        }

    def classify(self, query: str) -> int:
        """
        分类查询复杂度

        Args:
            query: 查询文本

        Returns:
            复杂度分数 (1-10)
        """
        score = 0.0

        # 特征 1: 查询长度
        length = len(query)
        if length < 20:
            length_score = 2
        elif length < 50:
            length_score = 5
        elif length < 100:
            length_score = 7
        else:
            length_score = 9

        score += length_score * self.features["length"]

        # 特征 2: 多部分查询（包含 "并且"、"然后"、"同时" 等）
        multi_part_keywords = ["并且", "然后", "同时", "以及", "另外", "还有"]
        multi_part_count = sum(1 for kw in multi_part_keywords if kw in query)
        multi_part_score = min(multi_part_count * 3, 10)

        score += multi_part_score * self.features["multi_part"]

        # 特征 3: 推理词汇
        reasoning_keywords = ["为什么", "如何", "原因", "解释", "分析", "比较", "区别"]
        reasoning_count = sum(1 for kw in reasoning_keywords if kw in query)
        reasoning_score = min(reasoning_count * 3, 10)

        score += reasoning_score * self.features["reasoning"]

        # 特征 4: 计算需求
        calculation_keywords = ["计算", "增长率", "百分比", "总和", "平均", "统计"]
        calculation_count = sum(1 for kw in calculation_keywords if kw in query)
        calculation_score = min(calculation_count * 4, 10)

        score += calculation_score * self.features["calculation"]

        # 归一化到 1-10
        final_score = max(1, min(10, int(score)))

        logger.debug(
            f"Query complexity: {final_score} (length={length_score}, "
            f"multi_part={multi_part_score}, reasoning={reasoning_score}, calc={calculation_score})"
        )

        return final_score


class ModelSelector:
    """智能模型选择器"""

    def __init__(self):
        """初始化选择器"""
        self.classifier = QueryComplexityClassifier()

        # 租户等级配置
        self.tier_configs = {
            "free": {
                "default_model": "gpt-3.5-turbo",
                "max_model": "gpt-3.5-turbo",
                "daily_budget": 1.0,  # $1/天
            },
            "standard": {
                "default_model": "gpt-3.5-turbo",
                "max_model": "gpt-4-turbo",
                "daily_budget": 10.0,  # $10/天
            },
            "premium": {
                "default_model": "gpt-4-turbo",
                "max_model": "gpt-4-turbo",
                "daily_budget": 50.0,  # $50/天
            },
            "enterprise": {
                "default_model": "gpt-4-turbo",
                "max_model": "gpt-4-turbo",
                "daily_budget": 200.0,  # $200/天
            },
        }

        # 模型定价（每 1K tokens，USD）
        self.pricing = {
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        }

    def select_model(
        self,
        query: str,
        tier: TierType = "standard",
        daily_cost_so_far: float = 0.0,
        force_model: str | None = None,
    ) -> dict[str, any]:
        """
        选择最优模型

        Args:
            query: 查询文本
            tier: 租户等级
            daily_cost_so_far: 今日已花费（USD）
            force_model: 强制使用的模型（可选）

        Returns:
            {
                "model": "gpt-4-turbo",
                "reason": "complex query",
                "estimated_cost": 0.05
            }
        """
        # 强制模型
        if force_model:
            return {
                "model": force_model,
                "reason": "forced",
                "estimated_cost": self._estimate_cost(force_model, query),
            }

        # 获取租户配置
        tier_config = self.tier_configs.get(tier, self.tier_configs["standard"])
        daily_budget = tier_config["daily_budget"]
        max_model = tier_config["max_model"]
        tier_config["default_model"]

        # 检查预算
        if daily_cost_so_far >= daily_budget * 0.9:  # 达到 90% 预算
            logger.warning(
                f"Budget nearly exhausted: {daily_cost_so_far:.2f}/{daily_budget:.2f}, using cheapest model"
            )
            return {
                "model": "gpt-3.5-turbo",
                "reason": "budget_limit",
                "estimated_cost": self._estimate_cost("gpt-3.5-turbo", query),
            }

        # 分析查询复杂度
        complexity = self.classifier.classify(query)

        # 选择策略
        if complexity <= 4:
            # 简单查询 → 最便宜的模型
            model = "gpt-3.5-turbo"
            reason = "simple_query"
        elif complexity <= 7:
            # 中等复杂度 → 根据租户等级决定
            if tier in ["premium", "enterprise"]:
                model = "gpt-4-turbo"
                reason = "medium_complexity_premium_tier"
            else:
                model = "gpt-3.5-turbo"
                reason = "medium_complexity_standard_tier"
        else:
            # 复杂查询 → 最好的模型（受租户等级限制）
            model = max_model
            reason = "complex_query"

        # 预估成本
        estimated_cost = self._estimate_cost(model, query)

        # 二次检查：如果预估成本超出剩余预算，降级
        remaining_budget = daily_budget - daily_cost_so_far
        if estimated_cost > remaining_budget:
            logger.warning(
                f"Estimated cost {estimated_cost:.4f} exceeds remaining budget {remaining_budget:.4f}, downgrading"
            )
            model = "gpt-3.5-turbo"
            reason = "budget_protection"
            estimated_cost = self._estimate_cost(model, query)

        logger.info(
            f"Model selected: {model} (complexity={complexity}, tier={tier}, reason={reason})"
        )

        return {
            "model": model,
            "reason": reason,
            "complexity": complexity,
            "estimated_cost": estimated_cost,
        }

    def _estimate_cost(self, model: str, query: str, avg_output_tokens: int = 500) -> float:
        """
        预估查询成本

        Args:
            model: 模型名称
            query: 查询文本
            avg_output_tokens: 平均输出 tokens（默认 500）

        Returns:
            预估成本（USD）
        """
        # 简单估算 tokens（1 中文字符 ≈ 2 tokens）
        input_tokens = len(query) * 2

        pricing = self.pricing.get(model, self.pricing["gpt-4-turbo"])

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (avg_output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def get_model_config(self, model: str) -> dict[str, any]:
        """
        获取模型配置

        Args:
            model: 模型名称

        Returns:
            模型配置
        """
        configs = {
            "gpt-4-turbo": {
                "model": "gpt-4-turbo-preview",
                "temperature": 0.7,
                "max_tokens": 2000,
                "top_p": 0.9,
            },
            "gpt-3.5-turbo": {
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 1500,
                "top_p": 0.9,
            },
            "claude-3-haiku": {
                "model": "claude-3-haiku-20240307",
                "temperature": 0.7,
                "max_tokens": 1500,
                "top_p": 0.9,
            },
        }

        return configs.get(model, configs["gpt-4-turbo"])


# 全局实例
_model_selector: ModelSelector | None = None


def get_model_selector() -> ModelSelector:
    """获取模型选择器实例"""
    global _model_selector
    if _model_selector is None:
        _model_selector = ModelSelector()
    return _model_selector
