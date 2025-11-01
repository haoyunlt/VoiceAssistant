"""
成本优化器
包含文本去重、Token 计数、成本计算和优化建议
"""

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# 尝试导入 Prometheus（可选依赖）
try:
    from prometheus_client import Counter as PromCounter
    from prometheus_client import Histogram

    PROMETHEUS_AVAILABLE = True

    # Prometheus 指标
    TOKENS_PROCESSED = PromCounter(
        "embedding_tokens_processed_total",
        "Total number of tokens processed",
        ["model", "tenant_id"],
    )
    EMBEDDING_COST = PromCounter(
        "embedding_cost_dollars_total",
        "Total embedding cost in dollars",
        ["model", "tenant_id"],
    )
    DEDUPLICATION_SAVINGS = PromCounter(
        "deduplication_savings_total",
        "Total texts saved by deduplication",
        ["tenant_id"],
    )
    TOKENS_PER_REQUEST = Histogram(
        "tokens_per_request",
        "Distribution of tokens per request",
        ["model"],
        buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000],
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available, metrics disabled")


class TokenCounter:
    """Token 计数器"""

    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        """
        初始化 Token 计数器

        Args:
            model_name: 模型名称（用于选择计数方法）
        """
        self.model_name = model_name

        # 尝试导入 tiktoken（精确计数）
        try:
            import tiktoken

            self.tiktoken = tiktoken
            self.use_tiktoken = True
            self.encoding = tiktoken.encoding_for_model(model_name)
            logger.info(f"TokenCounter initialized with tiktoken for {model_name}")
        except ImportError:
            self.tiktoken = None
            self.use_tiktoken = False
            logger.warning("tiktoken not available, using approximation")

    def count_tokens(self, text: str) -> int:
        """
        计算文本的 Token 数量

        Args:
            text: 输入文本

        Returns:
            Token 数量
        """
        if not text:
            return 0

        if self.use_tiktoken:
            # 精确计数
            return len(self.encoding.encode(text))
        else:
            # 近似计数
            return self._approximate_token_count(text)

    def count_tokens_batch(self, texts: list[str]) -> list[int]:
        """
        批量计算 Token 数量

        Args:
            texts: 文本列表

        Returns:
            Token 数量列表
        """
        return [self.count_tokens(text) for text in texts]

    def _approximate_token_count(self, text: str) -> int:
        """
        近似 Token 计数

        策略:
        - 中文字符: 每个字符约 1.5 tokens
        - 英文单词: 每个单词约 1.3 tokens
        - 数字和标点: 每个约 1 token

        Args:
            text: 输入文本

        Returns:
            近似 Token 数量
        """
        # 统计中文字符
        chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")

        # 统计英文单词
        english_words = len([word for word in text.split() if any(c.isalpha() for c in word)])

        # 统计数字
        numbers = len(re.findall(r"\d+", text))

        # 估算 Token 数
        estimated_tokens = int(chinese_chars * 1.5 + english_words * 1.3 + numbers * 1.0)

        return max(estimated_tokens, 1)  # 至少 1 token

    def estimate_cost(
        self,
        token_count: int,
        model: str = "bge-m3",
        cost_per_1k_tokens: float | None = None,
    ) -> float:
        """
        估算成本

        Args:
            token_count: Token 数量
            model: 模型名称
            cost_per_1k_tokens: 每 1k tokens 的成本

        Returns:
            成本（美元）
        """
        if cost_per_1k_tokens is None:
            cost_per_1k_tokens = self._get_model_cost(model)

        cost = (token_count / 1000) * cost_per_1k_tokens
        return cost

    def _get_model_cost(self, model: str) -> float:
        """
        获取模型的单价

        Args:
            model: 模型名称

        Returns:
            每 1k tokens 的成本（美元）
        """
        # 常见模型的价格（示例）
        model_prices = {
            # OpenAI
            "text-embedding-ada-002": 0.0001,
            "text-embedding-3-small": 0.00002,
            "text-embedding-3-large": 0.00013,
            # Cohere
            "embed-english-v3.0": 0.0001,
            "embed-multilingual-v3.0": 0.0001,
            # 本地模型（无成本，但有算力成本）
            "bge-m3": 0.0,
            "bge-large-zh": 0.0,
            "bge-base-zh": 0.0,
            # 其他
            "default": 0.0001,
        }

        return model_prices.get(model, model_prices["default"])


class TextDeduplicator:
    """文本去重器"""

    def __init__(self, use_hash: bool = True):
        """
        初始化文本去重器

        Args:
            use_hash: 是否使用哈希去重（更快但有极小碰撞概率）
        """
        self.use_hash = use_hash
        logger.info(f"TextDeduplicator initialized (use_hash={use_hash})")

    def deduplicate(self, texts: list[str]) -> tuple[list[str], list[int], dict[str, Any]]:
        """
        文本去重

        Args:
            texts: 文本列表

        Returns:
            (unique_texts, indices, stats)
            - unique_texts: 去重后的文本列表
            - indices: 原始索引到 unique 索引的映射
            - stats: 去重统计信息
        """
        if not texts:
            return [], [], {"original_count": 0, "unique_count": 0, "duplicates": 0}

        unique_texts = []
        text_to_index = {}  # 文本或哈希 -> unique 索引
        indices = []  # 原始索引 -> unique 索引的映射

        for text in texts:
            # 生成键（哈希或原文）
            key = self._hash_text(text) if self.use_hash else text

            # 检查是否已存在
            if key in text_to_index:
                # 重复文本
                unique_idx = text_to_index[key]
            else:
                # 新文本
                unique_idx = len(unique_texts)
                unique_texts.append(text)
                text_to_index[key] = unique_idx

            indices.append(unique_idx)

        stats = {
            "original_count": len(texts),
            "unique_count": len(unique_texts),
            "duplicates": len(texts) - len(unique_texts),
            "deduplication_rate": (len(texts) - len(unique_texts)) / len(texts) if texts else 0.0,
        }

        logger.debug(
            f"Deduplicated {len(texts)} texts -> {len(unique_texts)} unique "
            f"({stats['deduplication_rate']:.1%} duplicates)"
        )

        return unique_texts, indices, stats

    def deduplicate_with_reconstruction(self, texts: list[str]) -> tuple[list[str], list[int]]:
        """
        去重并返回重建映射

        Args:
            texts: 文本列表

        Returns:
            (unique_texts, reconstruction_indices)
            - unique_texts: 去重后的文本
            - reconstruction_indices: 用于重建原始顺序的索引
        """
        unique_texts, indices, _ = self.deduplicate(texts)
        return unique_texts, indices

    def _hash_text(self, text: str) -> str:
        """
        计算文本哈希

        Args:
            text: 文本

        Returns:
            哈希值
        """
        return hashlib.md5(text.encode()).hexdigest()


class CostCalculator:
    """成本计算器"""

    def __init__(self, token_counter: TokenCounter):
        """
        初始化成本计算器

        Args:
            token_counter: Token 计数器
        """
        self.token_counter = token_counter
        self.total_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0

        # 按模型和租户统计
        self.stats_by_model: dict[str, dict[str, Any]] = {}
        self.stats_by_tenant: dict[str, dict[str, Any]] = {}

        logger.info("CostCalculator initialized")

    def calculate_cost(
        self,
        texts: list[str],
        model: str,
        tenant_id: str = "default",
        cost_per_1k_tokens: float | None = None,
    ) -> dict[str, Any]:
        """
        计算成本

        Args:
            texts: 文本列表
            model: 模型名称
            tenant_id: 租户 ID
            cost_per_1k_tokens: 每 1k tokens 的成本

        Returns:
            成本信息
        """
        # 统计 Tokens
        token_counts = self.token_counter.count_tokens_batch(texts)
        total_tokens = sum(token_counts)

        # 计算成本
        total_cost = self.token_counter.estimate_cost(total_tokens, model, cost_per_1k_tokens)

        # 更新总计
        self.total_tokens += total_tokens
        self.total_cost += total_cost
        self.request_count += 1

        # 更新按模型统计
        if model not in self.stats_by_model:
            self.stats_by_model[model] = {
                "tokens": 0,
                "cost": 0.0,
                "requests": 0,
            }

        self.stats_by_model[model]["tokens"] += total_tokens
        self.stats_by_model[model]["cost"] += total_cost
        self.stats_by_model[model]["requests"] += 1

        # 更新按租户统计
        if tenant_id not in self.stats_by_tenant:
            self.stats_by_tenant[tenant_id] = {
                "tokens": 0,
                "cost": 0.0,
                "requests": 0,
            }

        self.stats_by_tenant[tenant_id]["tokens"] += total_tokens
        self.stats_by_tenant[tenant_id]["cost"] += total_cost
        self.stats_by_tenant[tenant_id]["requests"] += 1

        # 更新 Prometheus 指标
        if PROMETHEUS_AVAILABLE:
            TOKENS_PROCESSED.labels(model=model, tenant_id=tenant_id).inc(total_tokens)
            EMBEDDING_COST.labels(model=model, tenant_id=tenant_id).inc(total_cost)
            TOKENS_PER_REQUEST.labels(model=model).observe(total_tokens)

        result = {
            "text_count": len(texts),
            "total_tokens": total_tokens,
            "avg_tokens_per_text": total_tokens / len(texts) if texts else 0,
            "total_cost": total_cost,
            "cost_per_text": total_cost / len(texts) if texts else 0,
            "model": model,
            "tenant_id": tenant_id,
        }

        logger.debug(
            f"Cost calculated: {len(texts)} texts, {total_tokens} tokens, ${total_cost:.6f}"
        )

        return result

    def get_total_stats(self) -> dict[str, Any]:
        """
        获取总体统计

        Returns:
            统计信息
        """
        return {
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "request_count": self.request_count,
            "avg_tokens_per_request": self.total_tokens / self.request_count
            if self.request_count > 0
            else 0,
            "avg_cost_per_request": self.total_cost / self.request_count
            if self.request_count > 0
            else 0,
        }

    def get_stats_by_model(self) -> dict[str, dict[str, Any]]:
        """获取按模型的统计"""
        return self.stats_by_model

    def get_stats_by_tenant(self) -> dict[str, dict[str, Any]]:
        """获取按租户的统计"""
        return self.stats_by_tenant


class CostOptimizer:
    """成本优化器（整合去重、计数、计算）"""

    def __init__(
        self,
        model_name: str = "bge-m3",
        enable_deduplication: bool = True,
    ):
        """
        初始化成本优化器

        Args:
            model_name: 模型名称
            enable_deduplication: 是否启用去重
        """
        self.model_name = model_name
        self.enable_deduplication = enable_deduplication

        # 初始化组件
        self.token_counter = TokenCounter(model_name)
        self.deduplicator = TextDeduplicator(use_hash=True)
        self.cost_calculator = CostCalculator(self.token_counter)

        logger.info(f"CostOptimizer initialized: model={model_name}, dedup={enable_deduplication}")

    def optimize_and_calculate(
        self,
        texts: list[str],
        model: str | None = None,
        tenant_id: str = "default",
    ) -> tuple[list[str], list[int], dict[str, Any]]:
        """
        优化文本并计算成本

        策略:
        1. 文本去重
        2. 统计 Token
        3. 计算成本
        4. 返回优化后的文本和统计

        Args:
            texts: 文本列表
            model: 模型名称（默认使用初始化时的模型）
            tenant_id: 租户 ID

        Returns:
            (unique_texts, reconstruction_indices, stats)
        """
        if model is None:
            model = self.model_name

        # 1. 去重
        if self.enable_deduplication:
            unique_texts, indices, dedup_stats = self.deduplicator.deduplicate(texts)

            # 记录去重节省
            if PROMETHEUS_AVAILABLE:
                DEDUPLICATION_SAVINGS.labels(tenant_id=tenant_id).inc(dedup_stats["duplicates"])
        else:
            unique_texts = texts
            indices = list(range(len(texts)))
            dedup_stats = {
                "original_count": len(texts),
                "unique_count": len(texts),
                "duplicates": 0,
                "deduplication_rate": 0.0,
            }

        # 2. 计算成本（基于去重后的文本）
        cost_stats = self.cost_calculator.calculate_cost(unique_texts, model, tenant_id)

        # 3. 计算节省
        if self.enable_deduplication and dedup_stats["duplicates"] > 0:
            # 计算如果不去重的成本
            full_cost_stats = self.cost_calculator.calculate_cost(texts, model, tenant_id)

            savings = {
                "tokens_saved": full_cost_stats["total_tokens"] - cost_stats["total_tokens"],
                "cost_saved": full_cost_stats["total_cost"] - cost_stats["total_cost"],
                "savings_rate": (full_cost_stats["total_cost"] - cost_stats["total_cost"])
                / full_cost_stats["total_cost"]
                if full_cost_stats["total_cost"] > 0
                else 0.0,
            }
        else:
            savings = {
                "tokens_saved": 0,
                "cost_saved": 0.0,
                "savings_rate": 0.0,
            }

        # 4. 合并统计
        stats = {
            "deduplication": dedup_stats,
            "cost": cost_stats,
            "savings": savings,
            "optimization_enabled": self.enable_deduplication,
        }

        logger.info(
            f"Optimized {len(texts)} texts -> {len(unique_texts)} unique, "
            f"saved ${savings['cost_saved']:.6f} ({savings['savings_rate']:.1%})"
        )

        return unique_texts, indices, stats

    def get_optimization_report(self) -> dict[str, Any]:
        """
        生成优化报告

        Returns:
            优化报告
        """
        total_stats = self.cost_calculator.get_total_stats()
        model_stats = self.cost_calculator.get_stats_by_model()
        tenant_stats = self.cost_calculator.get_stats_by_tenant()

        report = {
            "total": total_stats,
            "by_model": model_stats,
            "by_tenant": tenant_stats,
            "recommendations": self._generate_recommendations(total_stats, model_stats),
        }

        return report

    def _generate_recommendations(
        self, total_stats: dict[str, Any], model_stats: dict[str, dict[str, Any]]
    ) -> list[str]:
        """
        生成优化建议

        Args:
            total_stats: 总体统计
            model_stats: 按模型统计

        Returns:
            建议列表
        """
        recommendations = []

        # 1. 检查成本
        total_cost = total_stats["total_cost"]
        if total_cost > 100:
            recommendations.append(
                f"💰 High cost detected (${total_cost:.2f}). "
                "Consider enabling caching or using cheaper models."
            )

        # 2. 检查是否启用去重
        if not self.enable_deduplication:
            recommendations.append("🔄 Deduplication is disabled. Enable it to reduce costs.")

        # 3. 检查模型选择
        for model, stats in model_stats.items():
            cost = stats["cost"]
            tokens = stats["tokens"]

            # 如果使用昂贵的模型但 Token 数很大
            if model.startswith("text-embedding-3-large") and tokens > 1000000:
                recommendations.append(
                    f"💡 Model '{model}' is expensive for high volume ({tokens:,} tokens). "
                    "Consider using 'text-embedding-3-small' or local models."
                )

            # 如果使用 OpenAI 但量很大
            if "openai" in model.lower() and cost > 50:
                recommendations.append(
                    f"💡 High OpenAI costs (${cost:.2f}). "
                    "Consider using local models (BGE-M3) for cost savings."
                )

        # 4. 检查平均 Token 数
        avg_tokens = total_stats["avg_tokens_per_request"]
        if avg_tokens > 1000:
            recommendations.append(
                f"📊 High average tokens per request ({avg_tokens:.0f}). "
                "Consider chunking texts into smaller pieces."
            )

        # 5. 通用建议
        if not recommendations:
            recommendations.append("✅ Cost optimization looks good! Continue monitoring.")

        return recommendations

    def reset_stats(self):
        """重置统计信息"""
        self.cost_calculator = CostCalculator(self.token_counter)
        logger.info("Cost optimizer stats reset")


class CostBudgetManager:
    """成本预算管理器"""

    def __init__(
        self,
        daily_budget: float = 100.0,
        monthly_budget: float = 3000.0,
        alert_threshold: float = 0.8,
    ):
        """
        初始化预算管理器

        Args:
            daily_budget: 每日预算（美元）
            monthly_budget: 每月预算（美元）
            alert_threshold: 告警阈值（百分比）
        """
        self.daily_budget = daily_budget
        self.monthly_budget = monthly_budget
        self.alert_threshold = alert_threshold

        self.daily_spent = 0.0
        self.monthly_spent = 0.0

        logger.info(
            f"CostBudgetManager initialized: daily=${daily_budget}, "
            f"monthly=${monthly_budget}, alert={alert_threshold:.0%}"
        )

    def record_cost(self, cost: float) -> dict[str, Any]:
        """
        记录成本

        Args:
            cost: 成本（美元）

        Returns:
            预算状态
        """
        self.daily_spent += cost
        self.monthly_spent += cost

        daily_usage_rate = self.daily_spent / self.daily_budget
        monthly_usage_rate = self.monthly_spent / self.monthly_budget

        status = {
            "daily_spent": self.daily_spent,
            "daily_budget": self.daily_budget,
            "daily_remaining": self.daily_budget - self.daily_spent,
            "daily_usage_rate": daily_usage_rate,
            "monthly_spent": self.monthly_spent,
            "monthly_budget": self.monthly_budget,
            "monthly_remaining": self.monthly_budget - self.monthly_spent,
            "monthly_usage_rate": monthly_usage_rate,
            "alerts": [],
        }

        # 检查是否超过告警阈值
        if daily_usage_rate >= self.alert_threshold:
            status["alerts"].append(
                f"⚠️  Daily budget {daily_usage_rate:.0%} used "
                f"(${self.daily_spent:.2f}/${self.daily_budget:.2f})"
            )

        if monthly_usage_rate >= self.alert_threshold:
            status["alerts"].append(
                f"⚠️  Monthly budget {monthly_usage_rate:.0%} used "
                f"(${self.monthly_spent:.2f}/${self.monthly_budget:.2f})"
            )

        # 检查是否超预算
        if self.daily_spent > self.daily_budget:
            status["alerts"].append("🚨 Daily budget exceeded!")

        if self.monthly_spent > self.monthly_budget:
            status["alerts"].append("🚨 Monthly budget exceeded!")

        return status

    def check_budget(self, estimated_cost: float) -> tuple[bool, str]:
        """
        检查是否可以执行（预算足够）

        Args:
            estimated_cost: 预估成本

        Returns:
            (can_proceed, message)
        """
        if self.daily_spent + estimated_cost > self.daily_budget:
            return (
                False,
                f"Daily budget exceeded (${self.daily_spent:.2f}/${self.daily_budget:.2f})",
            )

        if self.monthly_spent + estimated_cost > self.monthly_budget:
            return (
                False,
                f"Monthly budget exceeded (${self.monthly_spent:.2f}/${self.monthly_budget:.2f})",
            )

        return True, "OK"

    def reset_daily(self):
        """重置每日统计"""
        self.daily_spent = 0.0
        logger.info("Daily budget reset")

    def reset_monthly(self):
        """重置每月统计"""
        self.monthly_spent = 0.0
        logger.info("Monthly budget reset")
