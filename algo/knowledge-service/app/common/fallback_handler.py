"""
Fallback Handler - 降级处理器

实现服务降级策略，保证高可用性
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from app.core.metrics import record_fallback, service_degraded

logger = logging.getLogger(__name__)


class FallbackHandler:
    """降级处理器"""

    def __init__(
        self,
        error_threshold: int = 10,
        error_window_seconds: int = 60,
        recovery_window_seconds: int = 300,
    ):
        """
        初始化降级处理器

        Args:
            error_threshold: 错误阈值（触发降级）
            error_window_seconds: 错误窗口时间（秒）
            recovery_window_seconds: 恢复窗口时间（秒）
        """
        self.error_threshold = error_threshold
        self.error_window = timedelta(seconds=error_window_seconds)
        self.recovery_window = timedelta(seconds=recovery_window_seconds)

        # 错误追踪
        self.error_history: dict[str, list[datetime]] = {}

        # 降级状态
        self.degraded_components: dict[str, datetime] = {}

        # 降级锁
        self.locks: dict[str, asyncio.Lock] = {}

    async def execute_with_fallback(
        self,
        component: str,
        primary_func: Callable,
        fallback_func: Callable | None = None,
        fallback_value: Any = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        执行函数，失败时降级

        Args:
            component: 组件名称
            primary_func: 主函数
            fallback_func: 降级函数
            fallback_value: 降级返回值
            *args, **kwargs: 函数参数

        Returns:
            函数结果
        """
        # 检查是否已降级
        if self._is_degraded(component):
            logger.warning(f"Component {component} is degraded, using fallback")
            record_fallback(component, "auto_degraded")
            return await self._execute_fallback(
                component, fallback_func, fallback_value, *args, **kwargs
            )

        # 尝试执行主函数
        try:
            result = await primary_func(*args, **kwargs)
            self._record_success(component)
            return result

        except Exception as e:
            logger.error(f"Primary function failed for {component}: {e}")
            self._record_error(component)

            # 检查是否应该降级
            if self._should_degrade(component):
                await self._trigger_degradation(component)
                record_fallback(component, "threshold_exceeded")

            # 执行降级
            return await self._execute_fallback(
                component, fallback_func, fallback_value, *args, **kwargs
            )

    async def _execute_fallback(
        self,
        component: str,
        fallback_func: Callable | None,
        fallback_value: Any,
        *args,
        **kwargs,
    ) -> Any:
        """执行降级函数"""
        if fallback_func:
            try:
                result = await fallback_func(*args, **kwargs)
                logger.info(f"Fallback succeeded for {component}")
                return result
            except Exception as e:
                logger.error(f"Fallback function failed for {component}: {e}")

        # 返回默认值
        logger.warning(f"Using fallback value for {component}")
        return fallback_value

    def _record_error(self, component: str):
        """记录错误"""
        now = datetime.now()

        if component not in self.error_history:
            self.error_history[component] = []

        self.error_history[component].append(now)

        # 清理过期错误
        self.error_history[component] = [
            ts for ts in self.error_history[component] if now - ts < self.error_window
        ]

    def _record_success(self, component: str):
        """记录成功（用于恢复）"""
        # 如果已降级，检查是否可以恢复
        if component in self.degraded_components:
            degraded_since = self.degraded_components[component]
            if datetime.now() - degraded_since > self.recovery_window:
                self._recover_component(component)

    def _should_degrade(self, component: str) -> bool:
        """判断是否应该降级"""
        if component not in self.error_history:
            return False

        error_count = len(self.error_history[component])
        return error_count >= self.error_threshold

    def _is_degraded(self, component: str) -> bool:
        """判断组件是否已降级"""
        return component in self.degraded_components

    async def _trigger_degradation(self, component: str):
        """触发降级"""
        if component not in self.locks:
            self.locks[component] = asyncio.Lock()

        async with self.locks[component]:
            if component not in self.degraded_components:
                self.degraded_components[component] = datetime.now()
                service_degraded.labels(component=component).set(1)
                logger.warning(f"Component {component} degraded due to high error rate")

    def _recover_component(self, component: str):
        """恢复组件"""
        if component in self.degraded_components:
            del self.degraded_components[component]
            service_degraded.labels(component=component).set(0)
            logger.info(f"Component {component} recovered from degradation")

    def get_status(self) -> dict[str, Any]:
        """获取降级状态"""
        return {
            "degraded_components": {
                comp: {
                    "since": since.isoformat(),
                    "duration_seconds": (datetime.now() - since).total_seconds(),
                }
                for comp, since in self.degraded_components.items()
            },
            "error_history": {comp: len(errors) for comp, errors in self.error_history.items()},
        }


# 全局实例
_fallback_handler: FallbackHandler | None = None


def get_fallback_handler() -> FallbackHandler:
    """
    获取降级处理器实例（单例）

    Returns:
        FallbackHandler实例
    """
    global _fallback_handler

    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()

    return _fallback_handler


# ============= LLM降级策略 =============


class LLMFallbackStrategy:
    """LLM调用降级策略"""

    def __init__(self):
        """初始化降级策略"""
        # 模型降级链：gpt-4 -> gpt-4o-mini -> gpt-3.5-turbo
        self.model_chain = [
            {"name": "gpt-4o", "cost": 0.0025, "accuracy": 0.90},
            {"name": "gpt-4o-mini", "cost": 0.00015, "accuracy": 0.85},
            {"name": "gpt-3.5-turbo", "cost": 0.0005, "accuracy": 0.75},
        ]
        self.current_model_idx = 1  # 默认使用gpt-4o-mini

    def get_current_model(self) -> str:
        """获取当前模型"""
        return self.model_chain[self.current_model_idx]["name"]

    def downgrade(self) -> str | None:
        """降级到下一个模型"""
        if self.current_model_idx < len(self.model_chain) - 1:
            self.current_model_idx += 1
            new_model = self.model_chain[self.current_model_idx]["name"]
            logger.warning(f"LLM downgraded to {new_model}")
            return new_model
        return None

    def upgrade(self) -> str | None:
        """升级到上一个模型"""
        if self.current_model_idx > 0:
            self.current_model_idx -= 1
            new_model = self.model_chain[self.current_model_idx]["name"]
            logger.info(f"LLM upgraded to {new_model}")
            return new_model
        return None

    def get_model_info(self) -> dict[str, Any]:
        """获取当前模型信息"""
        return self.model_chain[self.current_model_idx]


# 全局LLM降级策略
_llm_fallback_strategy: LLMFallbackStrategy | None = None


def get_llm_fallback_strategy() -> LLMFallbackStrategy:
    """获取LLM降级策略实例"""
    global _llm_fallback_strategy

    if _llm_fallback_strategy is None:
        _llm_fallback_strategy = LLMFallbackStrategy()

    return _llm_fallback_strategy
