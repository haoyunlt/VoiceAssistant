"""
配置加密支持

提供配置敏感信息的加密/解密功能，支持：
- KMS 加密（AWS KMS, 阿里云 KMS）
- 本地密钥加密（用于开发环境）
- 环境变量加密值的自动解密
"""

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 尝试导入加密库
try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not installed. Config encryption disabled.")


class ConfigEncryption:
    """配置加密器"""

    def __init__(self, key: str | None = None, kms_enabled: bool = False):
        """
        初始化配置加密器

        Args:
            key: 加密密钥（Base64 编码），None 时从环境变量读取
            kms_enabled: 是否启用 KMS
        """
        self.kms_enabled = kms_enabled
        self.cipher = None

        if not CRYPTO_AVAILABLE:
            logger.warning("Crypto not available, encryption/decryption will be no-op")
            return

        if not kms_enabled:
            # 本地密钥加密
            encryption_key = key or os.getenv("CONFIG_ENCRYPTION_KEY")
            if encryption_key:
                try:
                    self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
                    logger.info("Local encryption initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize encryption: {e}")
        else:
            # KMS 加密（暂未实现，占位）
            logger.info("KMS encryption mode enabled (not yet implemented)")

    def encrypt(self, plaintext: str) -> str:
        """
        加密字符串

        Args:
            plaintext: 明文

        Returns:
            加密后的字符串（Base64 编码）
        """
        if not self.cipher:
            logger.warning("Encryption not available, returning plaintext")
            return plaintext

        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """
        解密字符串

        Args:
            ciphertext: 密文（Base64 编码）

        Returns:
            解密后的明文
        """
        if not self.cipher:
            logger.warning("Decryption not available, returning ciphertext")
            return ciphertext

        try:
            decoded = base64.b64decode(ciphertext.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ciphertext

    def decrypt_config(self, config_dict: dict[str, Any], encrypted_keys: list[str]) -> dict[str, Any]:
        """
        解密配置字典中的敏感字段

        Args:
            config_dict: 配置字典
            encrypted_keys: 需要解密的键列表（支持点号路径）

        Returns:
            解密后的配置字典
        """
        result = config_dict.copy()

        for key in encrypted_keys:
            value = self._get_nested_value(result, key)
            if value and isinstance(value, str):
                decrypted = self.decrypt(value)
                self._set_nested_value(result, key, decrypted)

        return result

    def _get_nested_value(self, d: dict, path: str) -> Any:
        """获取嵌套字典的值"""
        parts = path.split('.')
        current = d
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _set_nested_value(self, d: dict, path: str, value: Any):
        """设置嵌套字典的值"""
        parts = path.split('.')
        current = d
        for i, part in enumerate(parts[:-1]):  # noqa: B007
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value


def generate_encryption_key() -> str:
    """
    生成新的加密密钥

    Returns:
        Base64 编码的密钥
    """
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not installed")

    key = Fernet.generate_key()
    return key.decode()


# 全局加密器实例（懒加载）
_global_encryptor: ConfigEncryption | None = None


def get_encryptor() -> ConfigEncryption:
    """获取全局加密器实例"""
    global _global_encryptor
    if _global_encryptor is None:
        _global_encryptor = ConfigEncryption()
    return _global_encryptor


# 使用示例
if __name__ == "__main__":
    # 生成密钥
    key = generate_encryption_key()
    print(f"Generated key: {key}")

    # 加密/解密
    encryptor = ConfigEncryption(key=key)

    plaintext = "my_database_password_123"
    encrypted = encryptor.encrypt(plaintext)
    print(f"Encrypted: {encrypted}")

    decrypted = encryptor.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")

    assert plaintext == decrypted
    print("Encryption test passed!")
