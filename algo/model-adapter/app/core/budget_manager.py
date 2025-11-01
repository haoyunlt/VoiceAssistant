"""成本预算管理和告警."""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """预算配置."""

    tenant_id: str
    daily_limit_usd: float
    warning_threshold: float = 0.8  # 80%时告警
    auto_downgrade: bool = True  # 是否自动降级
    downgrade_quality: str = "low"  # 降级到的质量等级


@dataclass
class BudgetStatus:
    """预算状态."""

    tenant_id: str
    current_usage_usd: float
    daily_limit_usd: float
    remaining_usd: float
    usage_percent: float
    is_exceeded: bool
    is_warning: bool
    auto_downgraded: bool


class BudgetManager:
    """预算管理器."""

    def __init__(self):
        """初始化预算管理器."""
        # 预算配置存储 (tenant_id -> BudgetConfig)
        self._budgets: dict[str, BudgetConfig] = {}

        # 当天使用量存储 (tenant_id -> usage_usd)
        self._daily_usage: dict[str, float] = {}

        # 当天日期 (用于重置)
        self._current_date: str = self._get_today()

        # 告警钩子
        self._warning_hooks: list = []
        self._exceeded_hooks: list = []

        logger.info("BudgetManager initialized")

    def _get_today(self) -> str:
        """获取今天的日期字符串."""
        return datetime.now().strftime("%Y-%m-%d")

    def _reset_if_new_day(self):
        """如果是新的一天，重置使用量."""
        today = self._get_today()
        if today != self._current_date:
            logger.info(f"New day detected, resetting usage: {self._current_date} -> {today}")
            self._daily_usage.clear()
            self._current_date = today

    def set_budget(
        self,
        tenant_id: str,
        daily_limit_usd: float,
        warning_threshold: float = 0.8,
        auto_downgrade: bool = True,
        downgrade_quality: str = "low",
    ):
        """
        设置租户预算.

        Args:
            tenant_id: 租户ID
            daily_limit_usd: 每日限额(USD)
            warning_threshold: 告警阈值(0-1)
            auto_downgrade: 是否自动降级
            downgrade_quality: 降级到的质量等级
        """
        budget_config = BudgetConfig(
            tenant_id=tenant_id,
            daily_limit_usd=daily_limit_usd,
            warning_threshold=warning_threshold,
            auto_downgrade=auto_downgrade,
            downgrade_quality=downgrade_quality,
        )

        self._budgets[tenant_id] = budget_config

        logger.info(
            f"Budget set for tenant {tenant_id}: "
            f"${daily_limit_usd}/day, warning={warning_threshold * 100}%"
        )

    def record_usage(
        self,
        tenant_id: str,
        cost_usd: float,
    ):
        """
        记录使用量.

        Args:
            tenant_id: 租户ID
            cost_usd: 成本(USD)
        """
        self._reset_if_new_day()

        # 累加使用量
        current_usage = self._daily_usage.get(tenant_id, 0.0)
        new_usage = current_usage + cost_usd
        self._daily_usage[tenant_id] = new_usage

        logger.debug(f"Tenant {tenant_id} usage: ${current_usage:.6f} -> ${new_usage:.6f}")

        # 检查是否需要告警
        self._check_alerts(tenant_id, new_usage)

    def _check_alerts(self, tenant_id: str, current_usage: float):
        """
        检查是否需要触发告警.

        Args:
            tenant_id: 租户ID
            current_usage: 当前使用量
        """
        budget_config = self._budgets.get(tenant_id)
        if not budget_config:
            return

        usage_percent = current_usage / budget_config.daily_limit_usd

        # 超预算告警
        if usage_percent >= 1.0:
            logger.warning(
                f"🔴 Budget exceeded for tenant {tenant_id}: "
                f"${current_usage:.2f} / ${budget_config.daily_limit_usd:.2f}"
            )
            self._trigger_exceeded_alert(tenant_id, current_usage, budget_config)

        # 警告阈值告警
        elif usage_percent >= budget_config.warning_threshold:
            logger.warning(
                f"🟡 Budget warning for tenant {tenant_id}: "
                f"${current_usage:.2f} / ${budget_config.daily_limit_usd:.2f} "
                f"({usage_percent * 100:.1f}%)"
            )
            self._trigger_warning_alert(tenant_id, current_usage, budget_config)

    def _trigger_warning_alert(
        self,
        tenant_id: str,
        _current_usage: float,
        _budget_config: BudgetConfig,
    ):
        """触发警告告警."""
        status = self.get_status(tenant_id)

        for hook in self._warning_hooks:
            try:
                hook(status)
            except Exception as e:
                logger.error(f"Warning hook failed: {e}")

    def _trigger_exceeded_alert(
        self,
        tenant_id: str,
        _current_usage: float,
        _budget_config: BudgetConfig,
    ):
        """触发超预算告警."""
        status = self.get_status(tenant_id)

        for hook in self._exceeded_hooks:
            try:
                hook(status)
            except Exception as e:
                logger.error(f"Exceeded hook failed: {e}")

    def get_status(self, tenant_id: str) -> BudgetStatus:
        """
        获取预算状态.

        Args:
            tenant_id: 租户ID

        Returns:
            预算状态
        """
        self._reset_if_new_day()

        budget_config = self._budgets.get(tenant_id)
        if not budget_config:
            # 无预算限制
            return BudgetStatus(
                tenant_id=tenant_id,
                current_usage_usd=self._daily_usage.get(tenant_id, 0.0),
                daily_limit_usd=float("inf"),
                remaining_usd=float("inf"),
                usage_percent=0.0,
                is_exceeded=False,
                is_warning=False,
                auto_downgraded=False,
            )

        current_usage = self._daily_usage.get(tenant_id, 0.0)
        usage_percent = current_usage / budget_config.daily_limit_usd
        remaining = max(0, budget_config.daily_limit_usd - current_usage)

        is_exceeded = usage_percent >= 1.0
        is_warning = usage_percent >= budget_config.warning_threshold
        auto_downgraded = is_exceeded and budget_config.auto_downgrade

        return BudgetStatus(
            tenant_id=tenant_id,
            current_usage_usd=round(current_usage, 6),
            daily_limit_usd=budget_config.daily_limit_usd,
            remaining_usd=round(remaining, 6),
            usage_percent=round(usage_percent, 4),
            is_exceeded=is_exceeded,
            is_warning=is_warning,
            auto_downgraded=auto_downgraded,
        )

    def should_downgrade(self, tenant_id: str) -> tuple[bool, str]:
        """
        判断是否应该降级.

        Args:
            tenant_id: 租户ID

        Returns:
            (是否降级, 降级到的质量等级)
        """
        status = self.get_status(tenant_id)

        if status.auto_downgraded:
            budget_config = self._budgets.get(tenant_id)
            downgrade_quality = budget_config.downgrade_quality if budget_config else "low"
            return True, downgrade_quality

        return False, ""

    def register_warning_hook(self, hook: callable):
        """
        注册警告钩子.

        Args:
            hook: 钩子函数 (接收BudgetStatus)
        """
        self._warning_hooks.append(hook)

    def register_exceeded_hook(self, hook: callable):
        """
        注册超预算钩子.

        Args:
            hook: 钩子函数 (接收BudgetStatus)
        """
        self._exceeded_hooks.append(hook)

    def get_all_status(self) -> dict[str, BudgetStatus]:
        """
        获取所有租户的预算状态.

        Returns:
            租户ID -> 预算状态
        """
        all_status = {}

        # 有预算配置的租户
        for tenant_id in self._budgets:
            all_status[tenant_id] = self.get_status(tenant_id)

        # 有使用但无预算配置的租户
        for tenant_id in self._daily_usage:
            if tenant_id not in all_status:
                all_status[tenant_id] = self.get_status(tenant_id)

        return all_status


# Prometheus指标
from prometheus_client import Counter, Gauge  # noqa: E402

# 预算超限次数
budget_exceeded_total = Counter(
    "model_adapter_budget_exceeded_total",
    "Total budget exceeded events",
    ["tenant_id"],
)

# 预算警告次数
budget_warning_total = Counter(
    "model_adapter_budget_warning_total",
    "Total budget warning events",
    ["tenant_id"],
)

# 当前预算使用率
budget_usage_ratio = Gauge(
    "model_adapter_budget_usage_ratio",
    "Current budget usage ratio (0-1)",
    ["tenant_id"],
)

# 自动降级次数
auto_downgrade_total = Counter(
    "model_adapter_auto_downgrade_total",
    "Total auto-downgrade events",
    ["tenant_id"],
)


def update_budget_metrics(status: BudgetStatus):
    """
    更新预算指标.

    Args:
        status: 预算状态
    """
    budget_usage_ratio.labels(tenant_id=status.tenant_id).set(status.usage_percent)

    if status.is_exceeded:
        budget_exceeded_total.labels(tenant_id=status.tenant_id).inc()

    if status.is_warning:
        budget_warning_total.labels(tenant_id=status.tenant_id).inc()

    if status.auto_downgraded:
        auto_downgrade_total.labels(tenant_id=status.tenant_id).inc()


# 全局预算管理器实例
_budget_manager: BudgetManager | None = None


def get_budget_manager() -> BudgetManager:
    """获取全局预算管理器实例."""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager


async def send_budget_alert_webhook(status: BudgetStatus, alert_type: str):
    """
    发送预算告警到Webhook.

    Args:
        status: 预算状态
        alert_type: 告警类型 (warning/exceeded)
    """
    # TODO: 集成到notification-service
    logger.warning(
        f"Budget alert [{alert_type}]: tenant={status.tenant_id}, "
        f"usage=${status.current_usage_usd:.2f}, "
        f"limit=${status.daily_limit_usd:.2f}, "
        f"percent={status.usage_percent * 100:.1f}%"
    )
