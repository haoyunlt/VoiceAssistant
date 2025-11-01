"""
配置审计日志

记录配置的加载、更新、访问等操作，用于安全审计和问题排查。
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ConfigAuditLogger:
    """配置审计日志记录器"""

    def __init__(self, service_name: str, enable_audit: bool = True):
        """
        初始化审计日志记录器

        Args:
            service_name: 服务名称
            enable_audit: 是否启用审计
        """
        self.service_name = service_name
        self.enable_audit = enable_audit
        self.audit_logger = logging.getLogger(f"{service_name}.config.audit")

    def log_config_load(
        self,
        source: str,
        success: bool,
        config_keys: list[str] | None = None,
        error: str | None = None,
    ):
        """
        记录配置加载事件

        Args:
            source: 配置来源（local/nacos/env）
            success: 是否成功
            config_keys: 加载的配置键列表
            error: 错误信息
        """
        if not self.enable_audit:
            return

        event = {
            "event_type": "config_load",
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "source": source,
            "success": success,
            "config_keys_count": len(config_keys) if config_keys else 0,
        }

        if error:
            event["error"] = error

        self._log_event(event, level=logging.INFO if success else logging.ERROR)

    def log_config_update(
        self,
        source: str,
        updated_keys: list[str],
        user: str | None = None,
    ):
        """
        记录配置更新事件

        Args:
            source: 配置来源
            updated_keys: 更新的配置键列表
            user: 操作用户
        """
        if not self.enable_audit:
            return

        event = {
            "event_type": "config_update",
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "source": source,
            "updated_keys": updated_keys,
            "updated_keys_count": len(updated_keys),
        }

        if user:
            event["user"] = user

        self._log_event(event, level=logging.WARNING)  # 配置更新是敏感操作

    def log_config_access(
        self,
        key: str,
        accessed_by: str | None = None,
        is_sensitive: bool = False,
    ):
        """
        记录配置访问事件（仅敏感配置）

        Args:
            key: 配置键
            accessed_by: 访问者（模块/函数名）
            is_sensitive: 是否敏感配置
        """
        if not self.enable_audit or not is_sensitive:
            return

        event = {
            "event_type": "config_access",
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "key": key,
            "is_sensitive": is_sensitive,
        }

        if accessed_by:
            event["accessed_by"] = accessed_by

        self._log_event(event, level=logging.DEBUG)

    def log_config_validation_failed(
        self,
        missing_keys: list[str] | None = None,
        invalid_keys: dict[str, str] | None = None,
    ):
        """
        记录配置验证失败事件

        Args:
            missing_keys: 缺失的配置键
            invalid_keys: 无效的配置键及原因
        """
        if not self.enable_audit:
            return

        event = {
            "event_type": "config_validation_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
        }

        if missing_keys:
            event["missing_keys"] = missing_keys

        if invalid_keys:
            event["invalid_keys"] = invalid_keys

        self._log_event(event, level=logging.ERROR)

    def _log_event(self, event: dict[str, Any], level: int):
        """
        记录审计事件

        Args:
            event: 事件字典
            level: 日志级别
        """
        try:
            # 结构化日志
            self.audit_logger.log(
                level,
                json.dumps(event, ensure_ascii=False),
                extra=event,
            )
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")


# 敏感配置键模式（用于自动识别）
SENSITIVE_KEY_PATTERNS = [
    "password",
    "secret",
    "token",
    "key",
    "credential",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
]


def is_sensitive_key(key: str) -> bool:
    """
    判断配置键是否敏感

    Args:
        key: 配置键

    Returns:
        是否敏感
    """
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS)


# 示例：集成到 UnifiedConfig
def create_audited_config(service_name: str, enable_audit: bool = True):
    """
    创建带审计的配置管理器

    Args:
        service_name: 服务名称
        enable_audit: 是否启用审计

    Returns:
        配置管理器和审计日志记录器
    """
    from unified_config import create_config

    audit_logger = ConfigAuditLogger(service_name, enable_audit)

    # 记录配置加载
    try:
        config = create_config(service_name)
        audit_logger.log_config_load(
            source="multiple",
            success=True,
            config_keys=list(config._config_data.keys()),
        )
        return config, audit_logger
    except Exception as e:
        audit_logger.log_config_load(
            source="multiple",
            success=False,
            error=str(e),
        )
        raise
