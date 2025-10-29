"""适配器管理器 - 负责适配器的生命周期管理."""

import logging
from typing import Any

from app.core.exceptions import ProviderNotAvailableError, ProviderNotFoundError
from app.core.settings import Settings

logger = logging.getLogger(__name__)


class AdapterManager:
    """适配器管理器."""

    def __init__(self, settings: Settings):
        """
        初始化适配器管理器.

        Args:
            settings: 应用配置
        """
        self.settings = settings
        self._adapters: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化所有适配器."""
        if self._initialized:
            logger.warning("AdapterManager already initialized")
            return

        logger.info("Initializing adapters...")

        # OpenAI
        if self.settings.openai_api_key and self.settings.openai_enabled:
            try:
                from app.adapters.openai_adapter import OpenAIAdapter

                self._adapters["openai"] = OpenAIAdapter(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url,
                )
                logger.info("OpenAI adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI adapter: {e}")

        # Claude
        if self.settings.anthropic_api_key and self.settings.anthropic_enabled:
            try:
                from app.adapters.claude_adapter import ClaudeAdapter

                self._adapters["claude"] = ClaudeAdapter(
                    api_key=self.settings.anthropic_api_key
                )
                logger.info("Claude adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Claude adapter: {e}")

        # 智谱AI
        if self.settings.zhipu_api_key and self.settings.zhipu_enabled:
            try:
                from app.services.providers.zhipu_adapter import ZhipuAdapter

                self._adapters["zhipu"] = ZhipuAdapter(
                    api_key=self.settings.zhipu_api_key
                )
                logger.info("Zhipu adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Zhipu adapter: {e}")

        # 通义千问
        if self.settings.dashscope_api_key and self.settings.dashscope_enabled:
            try:
                from app.services.providers.qwen_adapter import QwenAdapter

                self._adapters["qwen"] = QwenAdapter(
                    api_key=self.settings.dashscope_api_key
                )
                logger.info("Qwen adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Qwen adapter: {e}")

        # 百度文心
        if (
            self.settings.baidu_api_key
            and self.settings.baidu_secret_key
            and self.settings.baidu_enabled
        ):
            try:
                from app.services.providers.baidu_adapter import BaiduAdapter

                self._adapters["baidu"] = BaiduAdapter(
                    api_key=self.settings.baidu_api_key,
                    secret_key=self.settings.baidu_secret_key,
                )
                logger.info("Baidu adapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Baidu adapter: {e}")

        self._initialized = True
        logger.info(f"AdapterManager initialized with {len(self._adapters)} adapters")

    async def shutdown(self) -> None:
        """关闭所有适配器."""
        logger.info("Shutting down adapters...")

        for provider, adapter in self._adapters.items():
            if hasattr(adapter, "close"):
                try:
                    await adapter.close()
                    logger.info(f"Closed {provider} adapter")
                except Exception as e:
                    logger.error(f"Error closing {provider} adapter: {e}")

        self._adapters.clear()
        self._initialized = False
        logger.info("All adapters shut down")

    def get_adapter(self, provider: str) -> Any:
        """
        获取适配器.

        Args:
            provider: 提供商名称

        Returns:
            适配器实例

        Raises:
            ProviderNotFoundError: 提供商不存在
            ProviderNotAvailableError: 提供商不可用
        """
        if not self._initialized:
            raise RuntimeError("AdapterManager not initialized")

        if provider not in self._adapters:
            raise ProviderNotFoundError(provider)

        adapter = self._adapters[provider]
        if adapter is None:
            raise ProviderNotAvailableError(provider, "Adapter is None")

        return adapter

    def list_providers(self) -> list[str]:
        """
        列出所有可用的提供商.

        Returns:
            提供商名称列表
        """
        return list(self._adapters.keys())

    async def check_provider_health(self, provider: str) -> bool:
        """
        检查提供商健康状态.

        Args:
            provider: 提供商名称

        Returns:
            是否健康
        """
        try:
            adapter = self.get_adapter(provider)
            if hasattr(adapter, "health_check"):
                is_healthy = await adapter.health_check()
                return bool(is_healthy)
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {provider}: {e}")
            return False

    async def get_all_provider_status(self) -> dict[str, dict[str, Any]]:
        """
        获取所有提供商的状态.

        Returns:
            提供商状态字典
        """
        status = {}

        for provider in self._adapters:
            try:
                is_healthy = await self.check_provider_health(provider)
                status[provider] = {
                    "available": True,
                    "healthy": is_healthy,
                }
            except Exception as e:
                status[provider] = {
                    "available": True,
                    "healthy": False,
                    "error": str(e),
                }

        return status

    @property
    def is_initialized(self) -> bool:
        """是否已初始化."""
        return self._initialized

    @property
    def adapter_count(self) -> int:
        """适配器数量."""
        return len(self._adapters)
