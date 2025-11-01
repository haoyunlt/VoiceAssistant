"""
请求级成本追踪中间件

功能：
- 追踪每个请求的 Token 使用和成本
- 按租户/用户/阶段（检索/生成/验证）拆分
- 预算告警
- 成本报告导出
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, List

from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Context variables for request-level tracking
_request_cost_context: ContextVar["CostTracker"] = ContextVar("request_cost_context", default=None)

# Prometheus metrics
cost_tracking_tokens_total = Counter(
    "cost_tracking_tokens_total",
    "Total tokens used",
    ["tenant_id", "phase", "model"],  # phase: embedding/generation/verification
)

cost_tracking_cost_usd = Counter(
    "cost_tracking_cost_usd",
    "Total cost in USD",
    ["tenant_id", "phase", "model"],
)

cost_tracking_request_cost_usd = Histogram(
    "cost_tracking_request_cost_usd",
    "Cost per request in USD",
    ["tenant_id"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)


@dataclass
class TokenUsage:
    """Token 使用记录"""

    phase: str  # embedding/generation/verification
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class CostSummary:
    """成本汇总"""

    total_cost_usd: float
    total_tokens: int
    by_phase: Dict[str, float]  # phase -> cost
    by_model: Dict[str, float]  # model -> cost
    details: List[TokenUsage]


class CostTracker:
    """成本追踪器（上下文管理器）"""

    def __init__(self, tenant_id: str = "default", user_id: str | None = None):
        """
        初始化成本追踪器

        Args:
            tenant_id: 租户 ID
            user_id: 用户 ID（可选）
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.usages: List[TokenUsage] = []

        # 模型定价（每 1K tokens，USD）
        self.pricing = {
            "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "text-embedding-3-small": {"input": 0.00002, "output": 0},
            "text-embedding-3-large": {"input": 0.00013, "output": 0},
            "text-embedding-ada-002": {"input": 0.0001, "output": 0},
        }

    def __enter__(self):
        """进入上下文"""
        _request_cost_context.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        # 汇总成本
        summary = self.get_summary()

        # 记录 Prometheus 指标
        cost_tracking_request_cost_usd.labels(tenant_id=self.tenant_id).observe(
            summary.total_cost_usd
        )

        # 日志记录
        logger.info(
            f"Request cost: tenant={self.tenant_id}, "
            f"cost=${summary.total_cost_usd:.4f}, "
            f"tokens={summary.total_tokens}, "
            f"by_phase={summary.by_phase}"
        )

        # 清理上下文
        _request_cost_context.set(None)

    def record(
        self,
        phase: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        tokens: int | None = None,
    ):
        """
        记录 Token 使用

        Args:
            phase: 阶段（embedding/generation/verification）
            model: 模型名称
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            tokens: 总 tokens（用于 embedding，等价于 input_tokens）
        """
        # 兼容：tokens 参数
        if tokens is not None:
            input_tokens = tokens

        # 获取定价
        pricing = self.pricing.get(model, self.pricing.get("gpt-4-turbo", {}))
        input_price = pricing.get("input", 0)
        output_price = pricing.get("output", 0)

        # 计算成本
        input_cost = (input_tokens / 1000) * input_price
        output_cost = (output_tokens / 1000) * output_price
        total_cost = input_cost + output_cost

        # 记录
        usage = TokenUsage(
            phase=phase,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total_cost,
        )
        self.usages.append(usage)

        # Prometheus 指标
        total_tokens = input_tokens + output_tokens
        cost_tracking_tokens_total.labels(
            tenant_id=self.tenant_id, phase=phase, model=model
        ).inc(total_tokens)

        cost_tracking_cost_usd.labels(tenant_id=self.tenant_id, phase=phase, model=model).inc(
            total_cost
        )

        logger.debug(
            f"Cost recorded: phase={phase}, model={model}, "
            f"tokens={total_tokens}, cost=${total_cost:.4f}"
        )

    def get_summary(self) -> CostSummary:
        """获取成本汇总"""
        total_cost = sum(u.cost_usd for u in self.usages)
        total_tokens = sum(u.input_tokens + u.output_tokens for u in self.usages)

        # 按阶段汇总
        by_phase = {}
        for usage in self.usages:
            by_phase[usage.phase] = by_phase.get(usage.phase, 0) + usage.cost_usd

        # 按模型汇总
        by_model = {}
        for usage in self.usages:
            by_model[usage.model] = by_model.get(usage.model, 0) + usage.cost_usd

        return CostSummary(
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            by_phase=by_phase,
            by_model=by_model,
            details=self.usages,
        )


class BudgetManager:
    """预算管理器"""

    def __init__(self):
        """初始化预算管理器"""
        # 租户预算配置（示例）
        self.budgets = {
            "default": {"daily": 10.0, "monthly": 300.0},
            # 可以从配置文件或数据库加载
        }

        # 当前使用（内存缓存，生产环境应使用 Redis）
        self.usage = {}

    def check_budget(self, tenant_id: str, estimated_cost: float) -> tuple[bool, str]:
        """
        检查预算

        Args:
            tenant_id: 租户 ID
            estimated_cost: 预估成本

        Returns:
            (是否允许, 原因)
        """
        budget = self.budgets.get(tenant_id, self.budgets["default"])
        daily_budget = budget["daily"]

        # 获取今日使用
        today_usage = self.get_today_usage(tenant_id)

        # 检查是否超出预算
        if today_usage + estimated_cost > daily_budget:
            return False, f"Daily budget exceeded: {today_usage:.2f}/{daily_budget:.2f}"

        # 检查是否接近预算（80%）
        if today_usage + estimated_cost > daily_budget * 0.8:
            logger.warning(
                f"Budget warning: tenant={tenant_id}, "
                f"usage={today_usage:.2f}/{daily_budget:.2f} (80%+)"
            )

        return True, "OK"

    def get_today_usage(self, tenant_id: str) -> float:
        """获取今日使用（应从 Redis 或数据库读取）"""
        # 简化实现：从内存读取
        # 生产环境应该：
        # 1. 从 Redis 读取今日累计
        # 2. 定时（每小时）从 Prometheus 同步
        return self.usage.get(tenant_id, 0.0)

    def record_usage(self, tenant_id: str, cost: float):
        """记录使用（应写入 Redis）"""
        self.usage[tenant_id] = self.usage.get(tenant_id, 0) + cost


# 全局实例
_budget_manager: BudgetManager | None = None


def get_budget_manager() -> BudgetManager:
    """获取预算管理器实例"""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager


def get_current_cost_tracker() -> CostTracker | None:
    """获取当前请求的成本追踪器"""
    return _request_cost_context.get()

