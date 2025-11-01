"""
熔断器 - Circuit Breaker

防止级联失败，提高系统韧性。

状态机：
- CLOSED (正常) → OPEN (熔断) → HALF_OPEN (半开) → CLOSED (恢复)

触发条件：
- 连续失败 5 次 → 熔断
- 熔断 60 秒后 → 半开
- 半开状态下成功 3 次 → 恢复
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    failure_threshold: int = 5  # 失败阈值
    timeout_seconds: int = 60  # 熔断超时（秒）
    half_open_max_calls: int = 3  # 半开状态最大调用次数


class CircuitBreaker:
    """熔断器"""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        """
        初始化熔断器

        Args:
            name: 熔断器名称（如 "llm_service", "retrieval_service"）
            config: 配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # 状态
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def call(self, func: Callable, *args, **kwargs):
        """
        调用函数（带熔断保护）

        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器开启
        """
        # 检查状态
        if self.state == CircuitState.OPEN:
            # 检查是否应该进入半开状态
            if time.time() - self.last_failure_time >= self.config.timeout_seconds:
                logger.info(f"Circuit breaker {self.name}: OPEN → HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        # 半开状态：限制调用次数
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is HALF_OPEN, max calls reached"
                )
            self.half_open_calls += 1

        # 执行调用
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """成功回调"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit breaker {self.name}: success in HALF_OPEN ({self.success_count}/{self.config.half_open_max_calls})"
            )

            # 检查是否应该恢复
            if self.success_count >= self.config.half_open_max_calls:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN → CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        else:
            # CLOSED 状态：重置失败计数
            self.failure_count = 0

    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态失败 → 立即熔断
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN → OPEN (failed)")
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # 检查是否达到熔断阈值
            if self.failure_count >= self.config.failure_threshold:
                logger.error(
                    f"Circuit breaker {self.name}: CLOSED → OPEN (threshold={self.config.failure_threshold})"
                )
                self.state = CircuitState.OPEN

    def get_state(self) -> Dict:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""

    pass


# 全局熔断器实例
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """获取或创建熔断器"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]

