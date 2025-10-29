"""
统一的密钥管理器

支持多种后端：
- HashiCorp Vault
- AWS Secrets Manager
- 环境变量（回退）
"""

import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretsBackend(ABC):
    """密钥后端抽象基类"""

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """获取密钥"""
        pass

    @abstractmethod
    def set_secret(self, key: str, value: str) -> bool:
        """设置密钥"""
        pass

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """删除密钥"""
        pass

    @abstractmethod
    def list_secrets(self) -> list:
        """列出所有密钥"""
        pass


class VaultBackend(SecretsBackend):
    """
    HashiCorp Vault 后端

    需要安装: pip install hvac
    """

    def __init__(
        self,
        vault_addr: str,
        vault_token: str | None = None,
        mount_point: str = "secret",
        path_prefix: str = "voiceassistant",
    ):
        """
        初始化 Vault 后端

        Args:
            vault_addr: Vault 地址
            vault_token: Vault Token
            mount_point: 挂载点
            path_prefix: 路径前缀
        """
        try:
            import hvac

            self.client = hvac.Client(
                url=vault_addr,
                token=vault_token or os.getenv("VAULT_TOKEN"),
            )

            if not self.client.is_authenticated():
                raise Exception("Vault authentication failed")

            self.mount_point = mount_point
            self.path_prefix = path_prefix

            logger.info(f"Vault backend initialized: {vault_addr}")

        except ImportError:
            raise ImportError("hvac package not installed. Install with: pip install hvac")
        except Exception as e:
            logger.error(f"Failed to initialize Vault: {e}")
            raise

    def get_secret(self, key: str) -> str | None:
        """从 Vault 获取密钥"""
        try:
            secret_path = f"{self.path_prefix}/{key}"
            response = self.client.secrets.kv.v2.read_secret_version(
                path=secret_path,
                mount_point=self.mount_point,
            )

            if response and "data" in response and "data" in response["data"]:
                return response["data"]["data"].get("value")

            return None

        except Exception as e:
            logger.error(f"Failed to get secret '{key}' from Vault: {e}")
            return None

    def set_secret(self, key: str, value: str) -> bool:
        """设置密钥到 Vault"""
        try:
            secret_path = f"{self.path_prefix}/{key}"
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path,
                secret={"value": value},
                mount_point=self.mount_point,
            )
            logger.info(f"Secret '{key}' set in Vault")
            return True

        except Exception as e:
            logger.error(f"Failed to set secret '{key}' in Vault: {e}")
            return False

    def delete_secret(self, key: str) -> bool:
        """从 Vault 删除密钥"""
        try:
            secret_path = f"{self.path_prefix}/{key}"
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=secret_path,
                mount_point=self.mount_point,
            )
            logger.info(f"Secret '{key}' deleted from Vault")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret '{key}' from Vault: {e}")
            return False

    def list_secrets(self) -> list:
        """列出所有密钥"""
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=self.path_prefix,
                mount_point=self.mount_point,
            )

            if response and "data" in response and "keys" in response["data"]:
                return response["data"]["keys"]

            return []

        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            return []


class AWSSecretsBackend(SecretsBackend):
    """
    AWS Secrets Manager 后端

    需要安装: pip install boto3
    """

    def __init__(self, region_name: str = "us-east-1", prefix: str = "voiceassistant/"):
        """
        初始化 AWS Secrets Manager 后端

        Args:
            region_name: AWS 区域
            prefix: 密钥前缀
        """
        try:
            import boto3

            self.client = boto3.client("secretsmanager", region_name=region_name)
            self.prefix = prefix

            logger.info(f"AWS Secrets Manager backend initialized: {region_name}")

        except ImportError:
            raise ImportError("boto3 package not installed. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Secrets Manager: {e}")
            raise

    def get_secret(self, key: str) -> str | None:
        """从 AWS Secrets Manager 获取密钥"""
        try:
            secret_name = f"{self.prefix}{key}"
            response = self.client.get_secret_value(SecretId=secret_name)

            return response.get("SecretString")

        except self.client.exceptions.ResourceNotFoundException:
            logger.warning(f"Secret '{key}' not found in AWS Secrets Manager")
            return None
        except Exception as e:
            logger.error(f"Failed to get secret '{key}' from AWS Secrets Manager: {e}")
            return None

    def set_secret(self, key: str, value: str) -> bool:
        """设置密钥到 AWS Secrets Manager"""
        try:
            secret_name = f"{self.prefix}{key}"

            # 尝试更新
            try:
                self.client.update_secret(SecretId=secret_name, SecretString=value)
            except self.client.exceptions.ResourceNotFoundException:
                # 如果不存在，创建新的
                self.client.create_secret(Name=secret_name, SecretString=value)

            logger.info(f"Secret '{key}' set in AWS Secrets Manager")
            return True

        except Exception as e:
            logger.error(f"Failed to set secret '{key}' in AWS Secrets Manager: {e}")
            return False

    def delete_secret(self, key: str) -> bool:
        """从 AWS Secrets Manager 删除密钥"""
        try:
            secret_name = f"{self.prefix}{key}"
            self.client.delete_secret(
                SecretId=secret_name,
                ForceDeleteWithoutRecovery=True,
            )
            logger.info(f"Secret '{key}' deleted from AWS Secrets Manager")
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret '{key}' from AWS Secrets Manager: {e}")
            return False

    def list_secrets(self) -> list:
        """列出所有密钥"""
        try:
            paginator = self.client.get_paginator("list_secrets")
            secrets = []

            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret["Name"]
                    if name.startswith(self.prefix):
                        secrets.append(name[len(self.prefix) :])

            return secrets

        except Exception as e:
            logger.error(f"Failed to list secrets from AWS Secrets Manager: {e}")
            return []


class EnvBackend(SecretsBackend):
    """环境变量后端（回退选项）"""

    def __init__(self, prefix: str = "SECRET_"):
        """
        初始化环境变量后端

        Args:
            prefix: 环境变量前缀
        """
        self.prefix = prefix
        logger.info("Environment variables backend initialized")

    def get_secret(self, key: str) -> str | None:
        """从环境变量获取密钥"""
        env_key = f"{self.prefix}{key.upper()}"
        value = os.getenv(env_key)

        if value:
            logger.debug(f"Secret '{key}' retrieved from environment variable '{env_key}'")
        else:
            logger.debug(f"Secret '{key}' not found in environment variables")

        return value

    def set_secret(self, key: str, value: str) -> bool:
        """设置环境变量（仅当前进程）"""
        env_key = f"{self.prefix}{key.upper()}"
        os.environ[env_key] = value
        logger.warning(
            f"Secret '{key}' set in environment (only for current process). "
            "Consider using a proper secrets manager."
        )
        return True

    def delete_secret(self, key: str) -> bool:
        """删除环境变量"""
        env_key = f"{self.prefix}{key.upper()}"
        if env_key in os.environ:
            del os.environ[env_key]
            logger.info(f"Secret '{key}' deleted from environment")
            return True
        return False

    def list_secrets(self) -> list:
        """列出所有密钥"""
        secrets = []
        for key in os.environ:
            if key.startswith(self.prefix):
                secrets.append(key[len(self.prefix) :].lower())
        return secrets


class SecretsManager:
    """
    统一密钥管理器

    自动选择合适的后端，支持多后端级联（先Vault，后环境变量）
    """

    def __init__(
        self,
        backend: SecretsBackend | None = None,
        fallback_to_env: bool = True,
    ):
        """
        初始化密钥管理器

        Args:
            backend: 主要后端（None则根据环境变量自动选择）
            fallback_to_env: 是否回退到环境变量
        """
        self.backend = backend
        self.env_backend = EnvBackend() if fallback_to_env else None

        # 如果没有提供后端，根据环境变量自动选择
        if self.backend is None:
            self.backend = self._auto_select_backend()

        logger.info(
            f"SecretsManager initialized: "
            f"backend={type(self.backend).__name__}, "
            f"fallback_to_env={fallback_to_env}"
        )

    def _auto_select_backend(self) -> SecretsBackend:
        """根据环境变量自动选择后端"""
        # 1. 尝试 Vault
        if os.getenv("VAULT_ENABLED", "false").lower() == "true":
            vault_addr = os.getenv("VAULT_ADDR")
            if vault_addr:
                try:
                    return VaultBackend(vault_addr=vault_addr)
                except Exception as e:
                    logger.warning(f"Failed to initialize Vault, falling back: {e}")

        # 2. 尝试 AWS Secrets Manager
        if os.getenv("AWS_SECRETS_ENABLED", "false").lower() == "true":
            try:
                region = os.getenv("AWS_REGION", "us-east-1")
                return AWSSecretsBackend(region_name=region)
            except Exception as e:
                logger.warning(f"Failed to initialize AWS Secrets Manager, falling back: {e}")

        # 3. 默认使用环境变量
        logger.info("Using environment variables as secrets backend")
        return EnvBackend()

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        """
        获取密钥（支持多后端级联）

        Args:
            key: 密钥名称
            default: 默认值

        Returns:
            密钥值，未找到则返回默认值
        """
        # 尝试主后端
        value = self.backend.get_secret(key)
        if value is not None:
            return value

        # 尝试环境变量回退
        if self.env_backend:
            value = self.env_backend.get_secret(key)
            if value is not None:
                return value

        # 返回默认值
        if default is not None:
            logger.debug(f"Secret '{key}' not found, using default value")

        return default

    def set_secret(self, key: str, value: str) -> bool:
        """设置密钥"""
        return self.backend.set_secret(key, value)

    def delete_secret(self, key: str) -> bool:
        """删除密钥"""
        return self.backend.delete_secret(key)

    def list_secrets(self) -> list:
        """列出所有密钥"""
        return self.backend.list_secrets()

    def get_dict(self, keys: list) -> dict[str, str | None]:
        """
        批量获取密钥

        Args:
            keys: 密钥名称列表

        Returns:
            密钥字典
        """
        return {key: self.get_secret(key) for key in keys}


# 全局单例
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """
    获取全局密钥管理器单例

    Returns:
        SecretsManager 实例
    """
    global _secrets_manager

    if _secrets_manager is None:
        _secrets_manager = SecretsManager()

    return _secrets_manager


# 便捷函数
def get_secret(key: str, default: str | None = None) -> str | None:
    """
    便捷函数：获取密钥

    Args:
        key: 密钥名称
        default: 默认值

    Returns:
        密钥值
    """
    return get_secrets_manager().get_secret(key, default)
