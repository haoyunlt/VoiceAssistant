"""
Budget Controller - 预算控制器

功能:
- 按租户/用户追踪成本
- 预算告警
- 自动降级策略
- 成本优化建议
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BudgetTier(Enum):
    """预算等级"""

    FREE = "free"  # 免费：$0.10/day
    BASIC = "basic"  # 基础：$1.00/day
    PRO = "pro"  # 专业：$10.00/day
    ENTERPRISE = "enterprise"  # 企业：无限制


class FallbackStrategy(Enum):
    """降级策略"""

    USE_CHEAPER_MODEL = "use_cheaper_model"  # 使用更便宜的模型
    REDUCE_MAX_TOKENS = "reduce_max_tokens"  # 减少 max_tokens
    SKIP_CRITIC = "skip_critic"  # 跳过 Critic 节点
    USE_CACHE_ONLY = "use_cache_only"  # 只使用缓存
    REJECT_REQUEST = "reject_request"  # 拒绝请求


class BudgetController:
    """
    预算控制器

    用法:
        controller = BudgetController(redis_client)

        # 检查预算
        if await controller.check_budget("tenant_123"):
            # 执行任务
            await controller.record_cost("tenant_123", 0.05)
        else:
            # 预算耗尽，应用降级策略
            strategy = await controller.get_fallback_strategy("tenant_123")
    """

    def __init__(
        self,
        redis_client: Any | None = None,
        default_tier: BudgetTier = BudgetTier.FREE,
        alert_threshold: float = 0.8,  # 80% 时告警
        enable_auto_fallback: bool = True,
    ):
        """
        初始化预算控制器

        Args:
            redis_client: Redis 客户端（用于存储预算数据）
            default_tier: 默认预算等级
            alert_threshold: 告警阈值（0-1）
            enable_auto_fallback: 是否启用自动降级
        """
        self.redis = redis_client
        self.default_tier = default_tier
        self.alert_threshold = alert_threshold
        self.enable_auto_fallback = enable_auto_fallback

        # 预算配置（美元/天）
        self.tier_budgets = {
            BudgetTier.FREE: 0.10,
            BudgetTier.BASIC: 1.00,
            BudgetTier.PRO: 10.00,
            BudgetTier.ENTERPRISE: float("inf"),
        }

        # 内存缓存（如果没有 Redis）
        self.memory_cache: dict[str, dict] = {}

        logger.info(
            f"BudgetController initialized (default_tier={default_tier.value}, "
            f"alert_threshold={alert_threshold})"
        )

    async def check_budget(self, tenant_id: str, estimated_cost: float = 0.0) -> bool:
        """
        检查预算是否充足

        Args:
            tenant_id: 租户 ID
            estimated_cost: 预估成本（美元）

        Returns:
            True: 预算充足, False: 预算不足
        """
        # 获取当前消耗
        current_usage = await self._get_daily_usage(tenant_id)

        # 获取预算
        budget = await self._get_budget(tenant_id)

        # 检查是否超预算
        if current_usage + estimated_cost > budget:
            logger.warning(
                f"[{tenant_id}] Budget exceeded: usage=${current_usage:.4f}, budget=${budget:.4f}"
            )
            return False

        # 检查是否触发告警
        usage_ratio = (current_usage + estimated_cost) / budget
        if usage_ratio >= self.alert_threshold:
            await self._trigger_alert(tenant_id, usage_ratio, current_usage, budget)

        return True

    async def record_cost(self, tenant_id: str, cost_usd: float, metadata: dict | None = None):
        """
        记录成本

        Args:
            tenant_id: 租户 ID
            cost_usd: 成本（美元）
            metadata: 额外元数据（如: mode, task_id, token_count）
        """
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"budget:usage:{tenant_id}:{today}"

        if self.redis:
            # 使用 Redis 存储
            await self.redis.incrbyfloat(key, cost_usd)
            await self.redis.expire(key, 86400 * 7)  # 保留 7 天

            # 记录详细信息
            if metadata:
                detail_key = f"budget:details:{tenant_id}:{today}"
                await self.redis.rpush(
                    detail_key,
                    {"timestamp": datetime.now().isoformat(), "cost": cost_usd, **metadata},
                )
                await self.redis.expire(detail_key, 86400 * 7)
        else:
            # 使用内存缓存
            if tenant_id not in self.memory_cache:
                self.memory_cache[tenant_id] = {"usage": 0.0, "date": today}

            if self.memory_cache[tenant_id]["date"] != today:
                # 新的一天，重置
                self.memory_cache[tenant_id] = {"usage": 0.0, "date": today}

            self.memory_cache[tenant_id]["usage"] += cost_usd

        logger.debug(f"[{tenant_id}] Recorded cost: ${cost_usd:.4f}")

    async def get_fallback_strategy(
        self, tenant_id: str, _current_cost: float = 0.0
    ) -> FallbackStrategy:
        """
        获取降级策略

        Args:
            tenant_id: 租户 ID
            current_cost: 当前任务预估成本

        Returns:
            降级策略
        """
        if not self.enable_auto_fallback:
            return FallbackStrategy.REJECT_REQUEST

        # 获取预算使用率
        usage = await self._get_daily_usage(tenant_id)
        budget = await self._get_budget(tenant_id)
        usage_ratio = usage / budget if budget > 0 else 1.0

        # 根据使用率选择策略
        if usage_ratio >= 0.95:
            # 95%+: 拒绝请求
            return FallbackStrategy.REJECT_REQUEST
        elif usage_ratio >= 0.90:
            # 90-95%: 只使用缓存
            return FallbackStrategy.USE_CACHE_ONLY
        elif usage_ratio >= 0.85:
            # 85-90%: 跳过 Critic
            return FallbackStrategy.SKIP_CRITIC
        elif usage_ratio >= 0.80:
            # 80-85%: 减少 max_tokens
            return FallbackStrategy.REDUCE_MAX_TOKENS
        else:
            # <80%: 使用更便宜的模型
            return FallbackStrategy.USE_CHEAPER_MODEL

    async def get_usage_report(self, tenant_id: str, days: int = 7) -> dict:
        """
        获取使用报告

        Args:
            tenant_id: 租户 ID
            days: 天数

        Returns:
            使用报告
        """
        daily_usage = []
        total_usage = 0.0

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            usage = await self._get_daily_usage(tenant_id, date)
            daily_usage.append({"date": date, "usage": usage})
            total_usage += usage

        budget = await self._get_budget(tenant_id)
        daily_budget = budget

        return {
            "tenant_id": tenant_id,
            "days": days,
            "total_usage": total_usage,
            "daily_average": total_usage / days,
            "daily_budget": daily_budget,
            "usage_ratio": total_usage / (daily_budget * days) if daily_budget > 0 else 1.0,
            "daily_usage": daily_usage,
        }

    async def get_optimization_suggestions(self, tenant_id: str) -> list[str]:
        """
        获取成本优化建议

        Args:
            tenant_id: 租户 ID

        Returns:
            优化建议列表
        """
        suggestions = []

        # 获取使用报告
        report = await self.get_usage_report(tenant_id, days=7)

        # 分析使用模式
        if report["usage_ratio"] > 0.9:
            suggestions.append("预算即将用尽，建议升级套餐或优化使用")

        if report["daily_average"] > report["daily_budget"] * 0.8:
            suggestions.append("每日平均消耗较高，建议：")
            suggestions.append("  - 使用更便宜的模型（如 GPT-3.5 代替 GPT-4）")
            suggestions.append("  - 启用语义缓存，减少重复查询")
            suggestions.append("  - 减少 max_tokens 限制")
            suggestions.append("  - 优化 Prompt，减少 Token 消耗")

        # 检查是否有突增
        if len(report["daily_usage"]) >= 2:
            recent = report["daily_usage"][0]["usage"]
            previous = report["daily_usage"][1]["usage"]
            if recent > previous * 1.5:
                suggestions.append("检测到用量突增，请检查是否有异常调用")

        return suggestions

    async def _get_daily_usage(self, tenant_id: str, date: str | None = None) -> float:
        """获取每日使用量"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = f"budget:usage:{tenant_id}:{date}"

        if self.redis:
            usage = await self.redis.get(key)
            return float(usage) if usage else 0.0
        else:
            if tenant_id in self.memory_cache and self.memory_cache[tenant_id]["date"] == date:
                return self.memory_cache[tenant_id]["usage"]
            return 0.0

    async def _get_budget(self, tenant_id: str) -> float:
        """获取租户预算"""
        # 从数据库或配置中获取租户的预算等级
        # 简化实现：使用默认等级
        tier = self.default_tier

        # 可以从 Redis 或数据库查询
        if self.redis:
            tier_str = await self.redis.get(f"budget:tier:{tenant_id}")
            if tier_str:
                tier = BudgetTier(tier_str)

        return self.tier_budgets[tier]

    async def _trigger_alert(
        self, tenant_id: str, usage_ratio: float, current_usage: float, budget: float
    ):
        """触发预算告警"""
        logger.warning(
            f"[{tenant_id}] Budget alert triggered: "
            f"usage_ratio={usage_ratio:.2%}, "
            f"current_usage=${current_usage:.4f}, "
            f"budget=${budget:.4f}"
        )

        # 发送告警（可以集成到通知服务）
        # await notification_service.send_alert(...)

        # 记录告警
        if self.redis:
            alert_key = f"budget:alerts:{tenant_id}"
            await self.redis.rpush(
                alert_key,
                {
                    "timestamp": datetime.now().isoformat(),
                    "usage_ratio": usage_ratio,
                    "current_usage": current_usage,
                    "budget": budget,
                },
            )
            await self.redis.expire(alert_key, 86400 * 30)  # 保留 30 天


# 全局预算控制器实例
_global_controller: BudgetController | None = None


def get_budget_controller() -> BudgetController:
    """获取全局预算控制器实例"""
    global _global_controller
    if _global_controller is None:
        _global_controller = BudgetController()
    return _global_controller


def set_budget_controller(controller: BudgetController):
    """设置全局预算控制器实例"""
    global _global_controller
    _global_controller = controller
