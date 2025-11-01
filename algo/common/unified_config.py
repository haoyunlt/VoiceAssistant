"""
统一配置管理 - 支持环境变量、本地文件、Nacos

提供统一的配置接口，支持多种配置源和优先级：
1. 环境变量（最高优先级）
2. Nacos 配置中心
3. 本地配置文件
4. 默认值（最低优先级）
"""

import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigMode(Enum):
    """配置模式"""

    LOCAL = "local"  # 本地文件
    NACOS = "nacos"  # Nacos 配置中心
    ENV = "env"  # 纯环境变量


class ConfigSource(ABC):
    """配置源抽象基类"""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """加载配置"""
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查配置源是否可用"""
        pass


class LocalConfigSource(ConfigSource):
    """本地文件配置源"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config_data: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """加载本地配置文件"""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.warning(f"Config file not found: {self.config_path}")
                return {}

            with open(config_file) as f:
                self.config_data = yaml.safe_load(f) or {}

            logger.info(f"✅ Loaded config from local file: {self.config_path}")
            return self.config_data

        except Exception as e:
            logger.error(f"Failed to load local config: {e}", exc_info=True)
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号路径）"""
        keys = key.split(".")
        value = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def is_available(self) -> bool:
        """检查本地文件是否存在"""
        return Path(self.config_path).exists()


class NacosConfigSource(ConfigSource):
    """Nacos 配置中心源"""

    def __init__(
        self,
        server_addr: str,
        namespace: str,
        group: str,
        data_id: str,
        username: str | None = None,
        password: str | None = None,
    ):
        self.server_addr = server_addr
        self.namespace = namespace
        self.group = group
        self.data_id = data_id
        self.username = username
        self.password = password
        self.config_data: dict[str, Any] = {}
        self.client = None

    def load(self) -> dict[str, Any]:
        """从 Nacos 加载配置"""
        try:
            import nacos

            # 创建 Nacos 客户端
            self.client = nacos.NacosClient(
                self.server_addr,
                namespace=self.namespace,
                username=self.username,
                password=self.password,
            )

            # 获取配置
            content = self.client.get_config(self.data_id, self.group)
            if not content:
                logger.warning(f"Empty config from Nacos: {self.group}/{self.data_id}")
                return {}

            # 解析 YAML
            self.config_data = yaml.safe_load(content) or {}

            logger.info(
                f"✅ Loaded config from Nacos: {self.group}/{self.data_id} "
                f"(namespace: {self.namespace})"
            )

            # 监听配置变更
            self._watch_config_change()

            return self.config_data

        except ImportError:
            logger.warning("nacos-sdk-python not installed, Nacos config disabled")
            return {}
        except Exception as e:
            logger.error(f"Failed to load Nacos config: {e}", exc_info=True)
            return {}

    def _watch_config_change(self):
        """监听配置变更"""
        if not self.client:
            return

        def callback(args):
            try:
                logger.info(f"🔄 Config changed: {self.group}/{self.data_id}")
                self.config_data = yaml.safe_load(args["content"]) or {}
                logger.info("✅ Config reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload config: {e}", exc_info=True)

        try:
            self.client.add_config_watcher(self.data_id, self.group, callback)
        except Exception as e:
            logger.warning(f"Failed to watch config change: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号路径）"""
        keys = key.split(".")
        value = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def is_available(self) -> bool:
        """检查 Nacos 是否可用"""
        return self.client is not None


class EnvConfigSource(ConfigSource):
    """环境变量配置源"""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix.upper() + "_" if prefix else ""

    def load(self) -> dict[str, Any]:
        """环境变量不需要预加载"""
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        """从环境变量获取配置"""
        # 转换点号路径为下划线：app.server.port -> APP_SERVER_PORT
        env_key = self.prefix + key.upper().replace(".", "_").replace("-", "_")
        value = os.getenv(env_key)

        if value is None:
            return default

        # 类型转换
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes", "on")
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        else:
            return value

    def is_available(self) -> bool:
        """环境变量始终可用"""
        return True


class UnifiedConfigManager:
    """
    统一配置管理器

    配置优先级（从高到低）：
    1. 环境变量
    2. Nacos 配置中心
    3. 本地配置文件
    4. 默认值
    """

    def __init__(
        self,
        service_name: str,
        config_path: str | None = None,
        env_prefix: str | None = None,
        allow_env_override: bool = True,
    ):
        """
        初始化统一配置管理器

        Args:
            service_name: 服务名称
            config_path: 配置文件路径
            env_prefix: 环境变量前缀（默认为服务名大写）
            allow_env_override: 是否允许环境变量覆盖
        """
        self.service_name = service_name
        self.config_path = config_path or f"./configs/{service_name}.yaml"
        self.env_prefix = env_prefix or service_name.upper().replace("-", "_")
        self.allow_env_override = allow_env_override

        # 配置源列表（按优先级）
        self.sources: list[ConfigSource] = []
        self.mode = self._detect_config_mode()

    def _detect_config_mode(self) -> ConfigMode:
        """检测配置模式"""
        mode_str = os.getenv("CONFIG_MODE", "local").lower()

        if mode_str == "nacos":
            return ConfigMode.NACOS
        elif mode_str == "env":
            return ConfigMode.ENV
        else:
            return ConfigMode.LOCAL

    def load(self):
        """加载配置"""
        # 1. 环境变量源（如果允许覆盖）
        if self.allow_env_override:
            env_source = EnvConfigSource(self.env_prefix)
            self.sources.insert(0, env_source)
            logger.debug("Added environment variable config source")

        # 2. 根据模式加载主配置源
        if self.mode == ConfigMode.NACOS:
            self._load_nacos_source()
        elif self.mode == ConfigMode.LOCAL:
            self._load_local_source()

        # 3. 加载所有配置源
        for source in self.sources:
            if source.is_available():
                source.load()

        logger.info(
            f"Config manager initialized: mode={self.mode.value}, sources={len(self.sources)}"
        )

    def _load_local_source(self):
        """加载本地配置源"""
        local_source = LocalConfigSource(self.config_path)
        self.sources.append(local_source)

    def _load_nacos_source(self):
        """加载 Nacos 配置源"""
        # 从环境变量或本地配置文件获取 Nacos 连接信息
        server_addr = os.getenv("NACOS_SERVER_ADDR", "localhost:8848")
        namespace = os.getenv("NACOS_NAMESPACE", "")
        group = os.getenv("NACOS_GROUP", "DEFAULT_GROUP")
        data_id = os.getenv("NACOS_DATA_ID", f"{self.service_name}.yaml")
        username = os.getenv("NACOS_USERNAME")
        password = os.getenv("NACOS_PASSWORD")

        nacos_source = NacosConfigSource(
            server_addr=server_addr,
            namespace=namespace,
            group=group,
            data_id=data_id,
            username=username,
            password=password,
        )
        self.sources.append(nacos_source)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（按优先级）

        Args:
            key: 配置键（支持点号路径，如 'app.server.port'）
            default: 默认值

        Returns:
            配置值
        """
        for source in self.sources:
            value = source.get(key, None)
            if value is not None:
                return value

        return default

    def get_string(self, key: str, default: str = "") -> str:
        """获取字符串配置"""
        return str(self.get(key, default))

    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数配置"""
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔配置"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取浮点数配置"""
        value = self.get(key, default)
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_list(self, key: str, default: list | None = None) -> list:
        """获取列表配置"""
        value = self.get(key, default or [])
        if isinstance(value, list):
            return value
        return default or []

    def get_dict(self, key: str, default: dict | None = None) -> dict:
        """获取字典配置"""
        value = self.get(key, default or {})
        if isinstance(value, dict):
            return value
        return default or {}

    def is_set(self, key: str) -> bool:
        """检查配置键是否存在"""
        return self.get(key) is not None

    def get_mode(self) -> ConfigMode:
        """获取配置模式"""
        return self.mode

    def validate_required(self, keys: list[str]) -> None:
        """
        验证必需的配置键

        Args:
            keys: 必需的配置键列表

        Raises:
            ValueError: 如果有配置键缺失
        """
        missing = [key for key in keys if not self.is_set(key)]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")


# ==================== 便捷函数 ====================


def create_config(
    service_name: str,
    config_path: str | None = None,
    required_keys: list[str] | None = None,
) -> UnifiedConfigManager:
    """
    创建并加载配置管理器

    Args:
        service_name: 服务名称
        config_path: 配置文件路径
        required_keys: 必需的配置键列表

    Returns:
        配置管理器实例
    """
    manager = UnifiedConfigManager(service_name=service_name, config_path=config_path)
    manager.load()

    if required_keys:
        manager.validate_required(required_keys)

    return manager
