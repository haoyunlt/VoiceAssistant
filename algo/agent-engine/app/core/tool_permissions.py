"""
工具权限体系
实现5级权限控制和审计日志
"""

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class ToolPermissionLevel(str, Enum):
    """工具权限级别"""

    LOW_RISK = "low_risk"  # 低风险：只读操作，无副作用
    MODERATE_RISK = "moderate_risk"  # 中等风险：有限的写操作
    HIGH_RISK = "high_risk"  # 高风险：重要的写操作或外部调用
    CRITICAL = "critical"  # 关键：数据修改、删除操作
    DANGEROUS = "dangerous"  # 危险：系统级操作、不可逆操作


class ToolPermissionManager:
    """工具权限管理器"""

    def __init__(self, redis_client=None, audit_enabled: bool = True):
        """
        初始化权限管理器

        Args:
            redis_client: Redis客户端（用于审计日志）
            audit_enabled: 是否启用审计日志
        """
        self.redis = redis_client
        self.audit_enabled = audit_enabled

        # 工具权限映射
        self.tool_permissions: dict[str, ToolPermissionLevel] = {}

        # 黑名单工具
        self.blacklisted_tools: set = set()

        # 审计日志键前缀
        self.audit_key_prefix = "tool_audit:"

        logger.info("ToolPermissionManager initialized")

    def register_tool_permission(self, tool_name: str, permission_level: ToolPermissionLevel):
        """
        注册工具权限

        Args:
            tool_name: 工具名称
            permission_level: 权限级别
        """
        self.tool_permissions[tool_name] = permission_level
        logger.info(f"Registered tool '{tool_name}' with permission '{permission_level}'")

    def get_tool_permission(self, tool_name: str) -> ToolPermissionLevel | None:
        """
        获取工具权限级别

        Args:
            tool_name: 工具名称

        Returns:
            权限级别，如果未注册返回None
        """
        return self.tool_permissions.get(tool_name)

    def is_tool_allowed(
        self,
        tool_name: str,
        max_permission: ToolPermissionLevel = ToolPermissionLevel.HIGH_RISK,
    ) -> bool:
        """
        检查工具是否允许使用

        Args:
            tool_name: 工具名称
            max_permission: 允许的最大权限级别

        Returns:
            是否允许
        """
        # 检查黑名单
        if tool_name in self.blacklisted_tools:
            logger.warning(f"Tool '{tool_name}' is blacklisted")
            return False

        # 获取工具权限
        tool_permission = self.get_tool_permission(tool_name)

        if tool_permission is None:
            # 未注册的工具，默认拒绝
            logger.warning(f"Tool '{tool_name}' is not registered")
            return False

        # 权限级别比较
        permission_order = [
            ToolPermissionLevel.LOW_RISK,
            ToolPermissionLevel.MODERATE_RISK,
            ToolPermissionLevel.HIGH_RISK,
            ToolPermissionLevel.CRITICAL,
            ToolPermissionLevel.DANGEROUS,
        ]

        tool_level_idx = permission_order.index(tool_permission)
        max_level_idx = permission_order.index(max_permission)

        return tool_level_idx <= max_level_idx

    def blacklist_tool(self, tool_name: str):
        """
        将工具加入黑名单

        Args:
            tool_name: 工具名称
        """
        self.blacklisted_tools.add(tool_name)
        logger.warning(f"Tool '{tool_name}' added to blacklist")

    def whitelist_tool(self, tool_name: str):
        """
        将工具移出黑名单

        Args:
            tool_name: 工具名称
        """
        if tool_name in self.blacklisted_tools:
            self.blacklisted_tools.remove(tool_name)
            logger.info(f"Tool '{tool_name}' removed from blacklist")

    async def log_tool_usage(
        self,
        tool_name: str,
        user_id: str | None,
        task_id: str,
        input_params: dict,
        result: dict | None = None,
        error: str | None = None,
    ):
        """
        记录工具使用审计日志

        Args:
            tool_name: 工具名称
            user_id: 用户ID
            task_id: 任务ID
            input_params: 输入参数
            result: 执行结果
            error: 错误信息
        """
        if not self.audit_enabled:
            return

        try:
            audit_log = {
                "tool_name": tool_name,
                "permission_level": self.get_tool_permission(tool_name).value
                if self.get_tool_permission(tool_name)
                else "unknown",
                "user_id": user_id,
                "task_id": task_id,
                "input_params": input_params,
                "result": result,
                "error": error,
                "timestamp": time.time(),
                "success": error is None,
            }

            # 记录到日志
            logger.info(
                f"Tool audit: {tool_name} by user {user_id} "
                f"(task={task_id}, success={audit_log['success']})"
            )

            # 如果有Redis，存储审计日志
            if self.redis:
                import json

                audit_key = f"{self.audit_key_prefix}{task_id}:{tool_name}"
                await self.redis.setex(
                    audit_key,
                    604800,
                    json.dumps(audit_log),  # 7天TTL
                )

        except Exception as e:
            logger.error(f"Failed to log tool usage: {e}")

    def get_tools_by_permission(self, permission_level: ToolPermissionLevel) -> list[str]:
        """
        获取指定权限级别的所有工具

        Args:
            permission_level: 权限级别

        Returns:
            工具名称列表
        """
        return [name for name, level in self.tool_permissions.items() if level == permission_level]

    def get_permission_summary(self) -> dict:
        """
        获取权限摘要统计

        Returns:
            权限统计信息
        """
        summary = {level.value: 0 for level in ToolPermissionLevel}

        for level in self.tool_permissions.values():
            summary[level.value] += 1

        return {
            "total_tools": len(self.tool_permissions),
            "blacklisted_tools": len(self.blacklisted_tools),
            "permission_distribution": summary,
        }


# 预定义的工具权限配置
DEFAULT_TOOL_PERMISSIONS = {
    # LOW_RISK: 只读操作
    "web_search": ToolPermissionLevel.LOW_RISK,
    "calculator": ToolPermissionLevel.LOW_RISK,
    "knowledge_query": ToolPermissionLevel.LOW_RISK,
    "weather_query": ToolPermissionLevel.LOW_RISK,
    "time_query": ToolPermissionLevel.LOW_RISK,
    # MODERATE_RISK: 有限写操作
    "send_email": ToolPermissionLevel.MODERATE_RISK,
    "create_note": ToolPermissionLevel.MODERATE_RISK,
    "update_calendar": ToolPermissionLevel.MODERATE_RISK,
    "send_notification": ToolPermissionLevel.MODERATE_RISK,
    # HIGH_RISK: 重要写操作
    "file_write": ToolPermissionLevel.HIGH_RISK,
    "api_call": ToolPermissionLevel.HIGH_RISK,
    "database_query": ToolPermissionLevel.HIGH_RISK,
    "code_executor": ToolPermissionLevel.HIGH_RISK,
    # CRITICAL: 数据修改/删除
    "file_delete": ToolPermissionLevel.CRITICAL,
    "database_update": ToolPermissionLevel.CRITICAL,
    "user_data_modify": ToolPermissionLevel.CRITICAL,
    # DANGEROUS: 系统级操作
    "system_command": ToolPermissionLevel.DANGEROUS,
    "shell_executor": ToolPermissionLevel.DANGEROUS,
    "database_drop": ToolPermissionLevel.DANGEROUS,
}


def create_default_permission_manager(
    redis_client=None, audit_enabled: bool = True
) -> ToolPermissionManager:
    """
    创建默认权限管理器

    Args:
        redis_client: Redis客户端
        audit_enabled: 是否启用审计

    Returns:
        配置好的权限管理器
    """
    manager = ToolPermissionManager(redis_client=redis_client, audit_enabled=audit_enabled)

    # 注册默认工具权限
    for tool_name, permission_level in DEFAULT_TOOL_PERMISSIONS.items():
        manager.register_tool_permission(tool_name, permission_level)

    logger.info(f"Created default permission manager with {len(DEFAULT_TOOL_PERMISSIONS)} tools")

    return manager
