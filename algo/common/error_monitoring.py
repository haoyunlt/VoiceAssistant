"""
错误码监控和指标收集

提供统一的错误码监控、统计和告警功能。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


# Prometheus 指标
error_total = Counter(
    "app_errors_total",
    "Total number of errors by service, category, code and endpoint",
    ["service", "category", "code", "endpoint"]
)

error_rate = Gauge(
    "app_error_rate",
    "Error rate by service and category",
    ["service", "category"]
)

error_response_time = Histogram(
    "app_error_response_time_seconds",
    "Response time for error requests",
    ["service", "category"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


class ErrorMonitor:
    """错误监控器"""

    def __init__(self, service_name: str, enable_monitoring: bool = True):
        """
        初始化错误监控器

        Args:
            service_name: 服务名称
            enable_monitoring: 是否启用监控
        """
        self.service_name = service_name
        self.enable_monitoring = enable_monitoring

        # 内存中的错误统计（用于快速查询和告警）
        self.error_counts: defaultdict[str, int] = defaultdict(int)
        self.error_timeline: list[tuple[datetime, int, str]] = []  # (timestamp, code, category)

        # 告警阈值配置
        self.alert_thresholds = {
            "GENERAL": {"count": 100, "window_minutes": 5},
            "BUSINESS": {"count": 50, "window_minutes": 5},
            "DATA": {"count": 30, "window_minutes": 5},
            "SERVICE": {"count": 20, "window_minutes": 5},
            "SYSTEM": {"count": 10, "window_minutes": 5},
        }

    def record_error(
        self,
        code: int,
        category: str,
        endpoint: str,
        response_time: float | None = None,
    ):
        """
        记录错误

        Args:
            code: 错误码
            category: 错误分类
            endpoint: 端点
            response_time: 响应时间（秒）
        """
        if not self.enable_monitoring:
            return

        # 更新 Prometheus 指标
        error_total.labels(
            service=self.service_name,
            category=category,
            code=str(code),
            endpoint=endpoint
        ).inc()

        if response_time is not None:
            error_response_time.labels(
                service=self.service_name,
                category=category
            ).observe(response_time)

        # 更新内存统计
        key = f"{category}:{code}"
        self.error_counts[key] += 1
        self.error_timeline.append((datetime.utcnow(), code, category))

        # 清理旧数据（保留最近1小时）
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self.error_timeline = [
            (ts, c, cat) for ts, c, cat in self.error_timeline
            if ts > cutoff
        ]

        # 检查是否需要告警
        self._check_alerts(category, code)

    def _check_alerts(self, category: str, code: int):
        """
        检查是否需要触发告警

        Args:
            category: 错误分类
            code: 错误码
        """
        threshold_config = self.alert_thresholds.get(category)
        if not threshold_config:
            return

        # 统计时间窗口内的错误数
        window = timedelta(minutes=threshold_config["window_minutes"])
        cutoff = datetime.utcnow() - window

        recent_errors = [
            (ts, c, cat) for ts, c, cat in self.error_timeline
            if ts > cutoff and cat == category
        ]

        if len(recent_errors) >= threshold_config["count"]:
            self._trigger_alert(category, code, len(recent_errors), threshold_config["window_minutes"])

    def _trigger_alert(self, category: str, code: int, count: int, window_minutes: int):
        """
        触发告警

        Args:
            category: 错误分类
            code: 错误码
            count: 错误数量
            window_minutes: 时间窗口（分钟）
        """
        alert_msg = (
            f"[ERROR ALERT] Service: {self.service_name}, "
            f"Category: {category}, Code: {code}, "
            f"Count: {count} in {window_minutes} minutes"
        )

        logger.error(
            alert_msg,
            extra={
                "alert_type": "error_threshold",
                "service": self.service_name,
                "category": category,
                "code": code,
                "count": count,
                "window_minutes": window_minutes,
            }
        )

        # TODO: 集成告警系统（钉钉、邮件、PagerDuty 等）

    def get_error_stats(self, category: str | None = None, minutes: int = 60) -> dict:
        """
        获取错误统计

        Args:
            category: 错误分类（None 表示所有分类）
            minutes: 时间窗口（分钟）

        Returns:
            错误统计字典
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)

        relevant_errors = [
            (ts, c, cat) for ts, c, cat in self.error_timeline
            if ts > cutoff and (category is None or cat == category)
        ]

        # 按分类统计
        category_counts: defaultdict[str, int] = defaultdict(int)
        code_counts: defaultdict[int, int] = defaultdict(int)

        for _, code, cat in relevant_errors:
            category_counts[cat] += 1
            code_counts[code] += 1

        return {
            "total": len(relevant_errors),
            "by_category": dict(category_counts),
            "by_code": dict(code_counts),
            "time_window_minutes": minutes,
        }


# 全局错误监控器（懒加载）
_global_monitor: ErrorMonitor | None = None


def get_error_monitor(service_name: str) -> ErrorMonitor:
    """
    获取全局错误监控器实例

    Args:
        service_name: 服务名称

    Returns:
        错误监控器实例
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ErrorMonitor(service_name)
    return _global_monitor
