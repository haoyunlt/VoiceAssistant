"""智能路由 - 基于成本和质量的模型选择."""

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.token_counter import CostCalculator, TokenCounter

logger = logging.getLogger(__name__)


# 模型质量分级配置
MODEL_TIERS = {
    "low": [
        "gpt-3.5-turbo",
        "gpt-4o-mini",
        "glm-3-turbo",
        "qwen-turbo",
        "claude-3-haiku-20240307",
    ],
    "medium": [
        "gpt-4-turbo",
        "gpt-4o",
        "glm-4",
        "qwen-plus",
        "claude-3-sonnet-20240229",
        "claude-3-5-sonnet-20240620",
    ],
    "high": [
        "gpt-4",
        "gpt-4-32k",
        "glm-4-plus",
        "qwen-max",
        "claude-3-opus-20240229",
    ],
}

# 模型到提供商的映射
MODEL_TO_PROVIDER = {
    # OpenAI
    "gpt-3.5-turbo": "openai",
    "gpt-4": "openai",
    "gpt-4-turbo": "openai",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4-32k": "openai",

    # Claude
    "claude-3-haiku-20240307": "claude",
    "claude-3-sonnet-20240229": "claude",
    "claude-3-opus-20240229": "claude",
    "claude-3-5-sonnet-20240620": "claude",

    # 智谱AI
    "glm-3-turbo": "zhipu",
    "glm-4": "zhipu",
    "glm-4-plus": "zhipu",

    # 通义千问
    "qwen-turbo": "qwen",
    "qwen-plus": "qwen",
    "qwen-max": "qwen",
}


@dataclass
class RouteResult:
    """路由结果."""

    provider: str
    model: str
    estimated_cost: float
    quality_tier: str
    reason: str


class SmartRouter:
    """智能路由器 - 根据质量要求选择最优性价比模型."""

    def __init__(
        self,
        model_tiers: Optional[dict[str, list[str]]] = None,
        cost_weight: float = 0.7,  # 成本权重 (0-1)
        quality_weight: float = 0.3,  # 质量权重 (0-1)
    ):
        """
        初始化智能路由器.

        Args:
            model_tiers: 模型分级配置
            cost_weight: 成本权重
            quality_weight: 质量权重
        """
        self.model_tiers = model_tiers or MODEL_TIERS
        self.cost_weight = cost_weight
        self.quality_weight = quality_weight

        logger.info(
            f"SmartRouter initialized: cost_weight={cost_weight}, "
            f"quality_weight={quality_weight}"
        )

    def route(
        self,
        quality_level: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
        available_providers: Optional[list[str]] = None,
    ) -> RouteResult:
        """
        路由到最优模型.

        Args:
            quality_level: 质量要求 (low/medium/high)
            messages: 消息列表
            max_tokens: 最大token数
            available_providers: 可用的提供商列表 (None表示全部可用)

        Returns:
            路由结果

        Raises:
            ValueError: 无可用模型
        """
        # 标准化质量等级
        quality_level = quality_level.lower()
        if quality_level not in self.model_tiers:
            logger.warning(f"Invalid quality level: {quality_level}, using 'medium'")
            quality_level = "medium"

        # 获取该质量等级的候选模型
        candidate_models = self.model_tiers[quality_level]

        # 过滤可用提供商的模型
        if available_providers:
            candidate_models = [
                model for model in candidate_models
                if MODEL_TO_PROVIDER.get(model) in available_providers
            ]

        if not candidate_models:
            raise ValueError(
                f"No available models for quality level: {quality_level}, "
                f"providers: {available_providers}"
            )

        # 估算输入token
        input_tokens = TokenCounter.count_message_tokens(messages)

        # 计算每个模型的成本
        model_costs = {}
        for model in candidate_models:
            cost_data = CostCalculator.calculate_cost(
                model,
                input_tokens,
                max_tokens,
            )
            model_costs[model] = cost_data["total_cost"]

        # 选择成本最低的模型
        best_model = min(model_costs.items(), key=lambda x: x[1])[0]
        best_cost = model_costs[best_model]
        best_provider = MODEL_TO_PROVIDER[best_model]

        logger.info(
            f"Route result: quality={quality_level}, model={best_model}, "
            f"provider={best_provider}, cost=${best_cost:.6f}"
        )

        return RouteResult(
            provider=best_provider,
            model=best_model,
            estimated_cost=best_cost,
            quality_tier=quality_level,
            reason=f"Lowest cost in {quality_level} tier",
        )

    def route_with_budget(
        self,
        messages: list[dict[str, str]],
        budget_usd: float,
        max_tokens: int = 1000,
        available_providers: Optional[list[str]] = None,
    ) -> RouteResult:
        """
        在预算限制下路由到最高质量的模型.

        Args:
            messages: 消息列表
            budget_usd: 预算(USD)
            max_tokens: 最大token数
            available_providers: 可用的提供商列表

        Returns:
            路由结果

        Raises:
            ValueError: 预算不足
        """
        # 估算输入token
        input_tokens = TokenCounter.count_message_tokens(messages)

        # 从高到低尝试每个质量等级
        for quality_level in ["high", "medium", "low"]:
            candidate_models = self.model_tiers[quality_level]

            # 过滤可用提供商的模型
            if available_providers:
                candidate_models = [
                    model for model in candidate_models
                    if MODEL_TO_PROVIDER.get(model) in available_providers
                ]

            # 找出预算内最便宜的模型
            for model in candidate_models:
                cost_data = CostCalculator.calculate_cost(
                    model,
                    input_tokens,
                    max_tokens,
                )
                cost = cost_data["total_cost"]

                if cost <= budget_usd:
                    provider = MODEL_TO_PROVIDER[model]

                    logger.info(
                        f"Budget route: quality={quality_level}, model={model}, "
                        f"cost=${cost:.6f} <= ${budget_usd}"
                    )

                    return RouteResult(
                        provider=provider,
                        model=model,
                        estimated_cost=cost,
                        quality_tier=quality_level,
                        reason=f"Best quality within budget ${budget_usd}",
                    )

        # 预算不足
        raise ValueError(
            f"Budget ${budget_usd} insufficient for any model "
            f"(min input tokens: {input_tokens})"
        )

    def compare_alternatives(
        self,
        current_model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1000,
    ) -> dict[str, dict]:
        """
        比较替代模型的成本.

        Args:
            current_model: 当前模型
            messages: 消息列表
            max_tokens: 最大token数

        Returns:
            替代方案对比
        """
        # 估算token
        input_tokens = TokenCounter.count_message_tokens(messages)

        # 当前模型成本
        current_cost = CostCalculator.calculate_cost(
            current_model,
            input_tokens,
            max_tokens,
        )

        # 找出当前模型的质量等级
        current_tier = None
        for tier, models in self.model_tiers.items():
            if current_model in models:
                current_tier = tier
                break

        if not current_tier:
            logger.warning(f"Model {current_model} not in any tier")
            return {}

        # 比较同等级其他模型
        alternatives = {}
        for model in self.model_tiers[current_tier]:
            if model == current_model:
                continue

            cost_data = CostCalculator.calculate_cost(
                model,
                input_tokens,
                max_tokens,
            )

            savings = current_cost["total_cost"] - cost_data["total_cost"]
            savings_percent = (savings / current_cost["total_cost"]) * 100

            alternatives[model] = {
                "provider": MODEL_TO_PROVIDER.get(model, "unknown"),
                "cost": cost_data["total_cost"],
                "savings": round(savings, 6),
                "savings_percent": round(savings_percent, 2),
                "quality_tier": current_tier,
            }

        # 按节省排序
        alternatives = dict(
            sorted(alternatives.items(), key=lambda x: x[1]["savings"], reverse=True)
        )

        return alternatives


# Prometheus指标
from prometheus_client import Counter, Histogram

# 路由次数
route_total = Counter(
    "model_adapter_route_total",
    "Total routing decisions",
    ["quality_tier", "selected_model"],
)

# 预算路由
budget_route_total = Counter(
    "model_adapter_budget_route_total",
    "Total budget-based routing decisions",
    ["quality_tier", "selected_model"],
)

# 路由节省成本
route_savings_usd_total = Counter(
    "model_adapter_route_savings_usd_total",
    "Total cost savings from smart routing",
)


def record_routing_decision(route_result: RouteResult, savings: float = 0.0):
    """
    记录路由决策.

    Args:
        route_result: 路由结果
        savings: 节省的成本(USD)
    """
    route_total.labels(
        quality_tier=route_result.quality_tier,
        selected_model=route_result.model,
    ).inc()

    if savings > 0:
        route_savings_usd_total.inc(savings)
