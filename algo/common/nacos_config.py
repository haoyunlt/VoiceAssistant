"""
Nacos 配置中心客户端 - Python 服务通用版
支持本地配置和 Nacos 配置中心两种模式
"""

import logging
import os
from collections.abc import Callable
from enum import Enum
from typing import Any

import yaml  # type: ignore[import]

logger = logging.getLogger(__name__)


class ConfigMode(str, Enum):
    """配置模式"""

    LOCAL = "local"
    NACOS = "nacos"


class NacosConfigManager:
    """Nacos 配置管理器"""

    def __init__(self) -> None:
        self.mode: ConfigMode = ConfigMode.LOCAL
        self.config_data: dict[str, Any] = {}
        self.nacos_client = None
        self.nacos_config: dict[str, Any] = {}
        self.local_config_path: str | None = None
        self.listeners: list[Callable] = []

    def load_config(self, config_path: str, service_name: str) -> dict[str, Any]:
        """
        加载配置

        Args:
            config_path: 本地配置文件路径（用于本地模式或Nacos连接配置）
            service_name: 服务名称（用作Nacos DataID的前缀）

        Returns:
            配置字典
        """
        # 从环境变量获取配置模式，默认为本地模式
        mode = os.getenv("CONFIG_MODE", "local").lower()
        self.mode = ConfigMode(mode)

        if self.mode == ConfigMode.NACOS:
            return self._load_from_nacos(config_path, service_name)
        else:
            return self._load_from_local(config_path)

    def _load_from_local(self, config_path: str) -> dict[str, Any]:
        """从本地文件加载配置"""
        self.local_config_path = config_path

        try:
            with open(config_path, encoding="utf-8") as f:
                self.config_data = yaml.safe_load(f) or {}
            logger.info(f"✅ Loaded config from local file: {config_path}")
            return self.config_data
        except Exception as e:
            logger.error(f"❌ Failed to load local config: {e}")
            raise

    def _load_from_nacos(self, config_path: str, service_name: str) -> dict[str, Any]:
        """从 Nacos 配置中心加载配置"""
        try:
            from nacos import NacosClient  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "nacos-sdk-python is required for Nacos mode. "
                "Install it with: pip install nacos-sdk-python"
            ) from None

        # 1. 从本地文件读取 Nacos 连接配置
        try:
            with open(config_path, encoding="utf-8") as f:
                local_config = yaml.safe_load(f) or {}
            self.nacos_config = local_config.get("nacos", {})
        except Exception as e:
            logger.error(f"❌ Failed to read Nacos connection config: {e}")
            raise

        # 2. 环境变量覆盖
        server_addr = os.getenv(
            "NACOS_SERVER_ADDR", self.nacos_config.get("server_addr", "localhost")
        )
        server_port = int(
            os.getenv("NACOS_SERVER_PORT", self.nacos_config.get("server_port", 8848))
        )
        namespace = os.getenv("NACOS_NAMESPACE", self.nacos_config.get("namespace", ""))
        group = os.getenv("NACOS_GROUP", self.nacos_config.get("group", "DEFAULT_GROUP"))
        data_id = os.getenv(
            "NACOS_DATA_ID", self.nacos_config.get("data_id", f"{service_name}.yaml")
        )
        username = os.getenv("NACOS_USERNAME", self.nacos_config.get("username", ""))
        password = os.getenv("NACOS_PASSWORD", self.nacos_config.get("password", ""))

        # 3. 创建 Nacos 客户端
        server_addresses = f"{server_addr}:{server_port}"

        try:
            self.nacos_client = NacosClient(
                server_addresses=server_addresses,
                namespace=namespace,
                username=username,
                password=password,
                log_level=logging.INFO,
            )
        except Exception as e:
            logger.error(f"❌ Failed to create Nacos client: {e}")
            raise

        # 4. 从 Nacos 获取配置
        try:
            if not self.nacos_client:
                raise RuntimeError("Nacos client not initialized")

            content = self.nacos_client.get_config(data_id, group)
            if not content:
                raise ValueError(f"Config not found: {group}/{data_id}")

            self.config_data = yaml.safe_load(content) or {}
            logger.info(f"✅ Loaded config from Nacos: {group}/{data_id} (namespace: {namespace})")
        except Exception as e:
            logger.error(f"❌ Failed to get config from Nacos: {e}")
            raise

        # 5. 监听配置变更
        try:
            if self.nacos_client and hasattr(self.nacos_client, "add_config_watcher"):
                self.nacos_client.add_config_watcher(data_id, group, self._on_config_change)
                logger.info(f"🔔 Watching config changes: {group}/{data_id}")
            else:
                logger.warning(
                    "⚠️  Nacos client does not support config watching (missing 'add_config_watcher')."
                )
        except Exception as e:
            logger.warning(f"⚠️  Failed to watch config changes: {e}")

        return self.config_data

    def _on_config_change(self, params: dict[str, Any]) -> None:
        """配置变更回调"""
        try:
            content = params.get("content", "")
            group = params.get("group", "")
            data_id = params.get("dataId", "")

            logger.info(f"🔄 Config changed: {group}/{data_id}")

            # 重新加载配置
            new_config: dict[str, Any] = yaml.safe_load(content) or {}
            self.config_data = new_config
            logger.info("✅ Config reloaded successfully")

            # 通知所有监听器
            for listener in self.listeners:
                try:
                    listener(self.config_data)
                except Exception as e:
                    logger.error(f"❌ Config change listener error: {e}")

        except Exception as e:
            logger.error(f"❌ Failed to handle config change: {e}")

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """添加配置变更监听器"""
        self.listeners.append(listener)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号分隔的嵌套key）"""
        keys = key.split(".")
        value: Any = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_all(self) -> dict[str, Any]:
        """获取所有配置"""
        return self.config_data

    def get_mode(self) -> ConfigMode:
        """获取配置模式"""
        return self.mode

    def close(self) -> None:
        """关闭配置管理器"""
        if self.nacos_client:
            try:
                # nacos-sdk-python 会自动清理资源
                self.nacos_client = None
                logger.info("✅ Nacos config manager closed")
            except Exception as e:
                logger.error(f"❌ Failed to close Nacos client: {e}")


# 全局配置管理器实例
_config_manager: NacosConfigManager | None = None


def init_config(config_path: str, service_name: str) -> dict[str, Any]:
    """
    初始化配置管理器（全局单例）

    Args:
        config_path: 配置文件路径
        service_name: 服务名称

    Returns:
        配置字典
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = NacosConfigManager()

    return _config_manager.load_config(config_path, service_name)


def get_config_manager() -> NacosConfigManager:
    """获取全局配置管理器"""
    global _config_manager

    if _config_manager is None:
        raise RuntimeError("Config manager not initialized. Call init_config() first.")

    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """获取配置值（便捷方法）"""
    return get_config_manager().get(key, default)
