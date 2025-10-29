import logging
from typing import Any

logger = logging.getLogger(__name__)

class AdapterRegistry:
    """
    适配器注册表，管理所有模型适配器。
    """

    def __init__(self):
        self.adapters: dict[str, Any] = {}
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
        }
        logger.info("AdapterRegistry initialized.")

    def register(self, provider: str, adapter: Any):
        """
        注册一个新的适配器。

        Args:
            provider: 提供商名称 (e.g., "openai", "anthropic", "azure")
            adapter: 适配器实例
        """
        self.adapters[provider] = adapter
        logger.info(f"Registered adapter for provider: {provider}")

    def get_adapter(self, provider: str) -> Any:
        """
        获取指定提供商的适配器。

        Args:
            provider: 提供商名称

        Returns:
            适配器实例

        Raises:
            KeyError: 如果提供商不存在
        """
        if provider not in self.adapters:
            raise KeyError(f"No adapter registered for provider: {provider}")
        return self.adapters[provider]

    def list_adapters(self) -> list[str]:
        """列出所有已注册的适配器"""
        return list(self.adapters.keys())

    async def get_stats(self) -> dict[str, Any]:
        """获取所有适配器的统计信息"""
        adapter_stats = {}
        for provider, adapter in self.adapters.items():
            if hasattr(adapter, "get_stats"):
                adapter_stats[provider] = await adapter.get_stats()

        return {
            **self.stats,
            "adapters": adapter_stats,
        }

    async def cleanup(self):
        """清理所有适配器资源"""
        logger.info("Cleaning up AdapterRegistry resources...")
        for provider, adapter in self.adapters.items():
            if hasattr(adapter, "close"):
                await adapter.close()
                logger.info(f"Closed adapter for provider: {provider}")
        logger.info("AdapterRegistry resources cleaned up.")
