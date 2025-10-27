"""适配器管理器单元测试."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.core.adapter_manager import AdapterManager
from app.core.exceptions import ProviderNotAvailableError, ProviderNotFoundError
from app.core.settings import Settings


@pytest.fixture
def mock_settings():
    """创建模拟配置."""
    settings = Mock(spec=Settings)
    settings.openai_api_key = "test-openai-key"
    settings.openai_base_url = None
    settings.openai_enabled = True
    settings.anthropic_api_key = None
    settings.anthropic_enabled = False
    settings.zhipu_api_key = None
    settings.zhipu_enabled = False
    settings.dashscope_api_key = None
    settings.dashscope_enabled = False
    settings.baidu_api_key = None
    settings.baidu_secret_key = None
    settings.baidu_enabled = False
    return settings


@pytest.fixture
def adapter_manager(mock_settings):
    """创建适配器管理器."""
    return AdapterManager(mock_settings)


class TestAdapterManager:
    """测试适配器管理器."""

    @pytest.mark.asyncio
    async def test_initialize(self, adapter_manager):
        """测试初始化."""
        with patch("app.core.adapter_manager.OpenAIAdapter") as MockAdapter:
            mock_instance = AsyncMock()
            MockAdapter.return_value = mock_instance

            await adapter_manager.initialize()

            assert adapter_manager.is_initialized
            assert adapter_manager.adapter_count == 1
            MockAdapter.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_adapter_success(self, adapter_manager):
        """测试成功获取适配器."""
        with patch("app.core.adapter_manager.OpenAIAdapter") as MockAdapter:
            mock_instance = AsyncMock()
            MockAdapter.return_value = mock_instance

            await adapter_manager.initialize()
            adapter = adapter_manager.get_adapter("openai")

            assert adapter is not None
            assert adapter == mock_instance

    def test_get_adapter_not_initialized(self, adapter_manager):
        """测试未初始化时获取适配器."""
        with pytest.raises(RuntimeError, match="not initialized"):
            adapter_manager.get_adapter("openai")

    @pytest.mark.asyncio
    async def test_get_adapter_not_found(self, adapter_manager):
        """测试获取不存在的适配器."""
        await adapter_manager.initialize()

        with pytest.raises(ProviderNotFoundError):
            adapter_manager.get_adapter("unknown_provider")

    @pytest.mark.asyncio
    async def test_list_providers(self, adapter_manager):
        """测试列出提供商."""
        with patch("app.core.adapter_manager.OpenAIAdapter"):
            await adapter_manager.initialize()
            providers = adapter_manager.list_providers()

            assert isinstance(providers, list)
            assert "openai" in providers

    @pytest.mark.asyncio
    async def test_check_provider_health(self, adapter_manager):
        """测试健康检查."""
        with patch("app.core.adapter_manager.OpenAIAdapter") as MockAdapter:
            mock_instance = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            MockAdapter.return_value = mock_instance

            await adapter_manager.initialize()
            is_healthy = await adapter_manager.check_provider_health("openai")

            assert is_healthy is True
            mock_instance.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_provider_status(self, adapter_manager):
        """测试获取所有提供商状态."""
        with patch("app.core.adapter_manager.OpenAIAdapter") as MockAdapter:
            mock_instance = AsyncMock()
            mock_instance.health_check = AsyncMock(return_value=True)
            MockAdapter.return_value = mock_instance

            await adapter_manager.initialize()
            status = await adapter_manager.get_all_provider_status()

            assert isinstance(status, dict)
            assert "openai" in status
            assert status["openai"]["available"] is True
            assert status["openai"]["healthy"] is True

    @pytest.mark.asyncio
    async def test_shutdown(self, adapter_manager):
        """测试关闭."""
        with patch("app.core.adapter_manager.OpenAIAdapter") as MockAdapter:
            mock_instance = AsyncMock()
            mock_instance.close = AsyncMock()
            MockAdapter.return_value = mock_instance

            await adapter_manager.initialize()
            await adapter_manager.shutdown()

            assert not adapter_manager.is_initialized
            assert adapter_manager.adapter_count == 0
            mock_instance.close.assert_called_once()
