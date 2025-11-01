"""
限流器 - Rate Limiter

基于令牌桶算法的分布式限流，支持：
- 租户级限流
- 用户级限流
- 端点级限流
- 动态限流（基于负载）
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """限流配置"""

    limit: int  # 限流数量
    window: int  # 时间窗口（秒）
    burst_multiplier: float = 1.5  # 突发倍数


class RateLimiter:
    """限流器（令牌桶算法）"""

    def __init__(self):
        """初始化限流器"""
        # 限流配置（生产环境应从配置文件加载）
        self.configs = {
            # 租户级限流
            "tenant:free": RateLimitConfig(limit=10, window=60),  # 10 QPS
            "tenant:standard": RateLimitConfig(limit=50, window=60),  # 50 QPS
            "tenant:premium": RateLimitConfig(limit=200, window=60),  # 200 QPS
            "tenant:enterprise": RateLimitConfig(limit=1000, window=60),  # 1000 QPS
            # 端点级限流
            "endpoint:/api/rag/query": RateLimitConfig(limit=100, window=60),
            "endpoint:/api/rag/v2/query": RateLimitConfig(limit=100, window=60),
        }

        # 令牌桶状态（内存实现，生产环境应使用 Redis）
        self.buckets: Dict[str, Dict] = {}

    def check_rate_limit(self, key: str, tier: str = "standard") -> tuple[bool, Dict]:
        """
        检查是否超出限流

        Args:
            key: 限流键（如 tenant:xxx 或 user:xxx）
            tier: 租户等级

        Returns:
            (是否允许, 限流信息)
        """
        # 获取配置
        config_key = f"{key.split(':')[0]}:{tier}"
        config = self.configs.get(config_key, self.configs["tenant:standard"])

        # 获取或创建令牌桶
        if key not in self.buckets:
            self.buckets[key] = {
                "tokens": config.limit,
                "last_update": time.time(),
                "limit": config.limit,
                "window": config.window,
            }

        bucket = self.buckets[key]

        # 计算令牌补充
        now = time.time()
        elapsed = now - bucket["last_update"]
        refill_rate = config.limit / config.window  # tokens per second
        new_tokens = elapsed * refill_rate

        # 更新令牌数（不超过上限）
        bucket["tokens"] = min(bucket["tokens"] + new_tokens, config.limit)
        bucket["last_update"] = now

        # 检查是否有可用令牌
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, {
                "allowed": True,
                "remaining": int(bucket["tokens"]),
                "limit": config.limit,
                "reset_after": config.window,
            }
        else:
            # 限流
            retry_after = int((1 - bucket["tokens"]) / refill_rate)
            logger.warning(f"Rate limit exceeded: key={key}, retry_after={retry_after}s")
            return False, {
                "allowed": False,
                "remaining": 0,
                "limit": config.limit,
                "retry_after": retry_after,
            }

    def get_tier_limit(self, tier: str) -> int:
        """获取租户等级的限流值"""
        config_key = f"tenant:{tier}"
        config = self.configs.get(config_key, self.configs["tenant:standard"])
        return config.limit


# 全局实例
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """获取限流器实例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

