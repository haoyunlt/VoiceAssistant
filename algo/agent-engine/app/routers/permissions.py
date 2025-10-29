"""
工具权限管理 API路由
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.tool_permissions import ToolPermissionLevel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/permissions", tags=["Tool Permissions"])

# 全局权限管理器（延迟初始化）
permission_manager = None


async def get_permission_manager():
    """获取或初始化权限管理器"""
    global permission_manager

    if permission_manager is None:
        logger.info("Initializing ToolPermissionManager...")
        from app.core.tool_permissions import create_default_permission_manager

        # TODO: 集成Redis客户端
        permission_manager = create_default_permission_manager(
            redis_client=None, audit_enabled=True
        )
        logger.info("ToolPermissionManager initialized")

    return permission_manager


class RegisterToolRequest(BaseModel):
    """注册工具权限请求"""

    tool_name: str = Field(..., description="工具名称")
    permission_level: ToolPermissionLevel = Field(..., description="权限级别")


class CheckPermissionRequest(BaseModel):
    """检查权限请求"""

    tool_name: str = Field(..., description="工具名称")
    max_permission: ToolPermissionLevel | None = Field(
        ToolPermissionLevel.HIGH_RISK, description="允许的最大权限级别"
    )


@router.post("/register")
async def register_tool_permission(request: RegisterToolRequest):
    """
    注册工具权限

    为工具设置权限级别。

    权限级别说明:
    - **low_risk**: 只读操作，无副作用（如搜索、查询）
    - **moderate_risk**: 有限的写操作（如发邮件、创建笔记）
    - **high_risk**: 重要的写操作（如文件写入、API调用）
    - **critical**: 数据修改/删除（如删除文件、更新数据库）
    - **dangerous**: 系统级操作（如执行Shell命令）

    示例:
    ```json
    {
        "tool_name": "web_search",
        "permission_level": "low_risk"
    }
    ```
    """
    manager = await get_permission_manager()

    try:
        manager.register_tool_permission(request.tool_name, request.permission_level)

        return {
            "success": True,
            "tool_name": request.tool_name,
            "permission_level": request.permission_level.value,
        }

    except Exception as e:
        logger.error(f"Failed to register tool permission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_permission(request: CheckPermissionRequest):
    """
    检查工具权限

    验证工具是否在允许的权限范围内。

    示例:
    ```json
    {
        "tool_name": "web_search",
        "max_permission": "high_risk"
    }
    ```

    返回:
    - allowed: 是否允许使用
    - tool_permission: 工具的权限级别
    - max_permission: 允许的最大权限级别
    - reason: 不允许的原因（如果applicable）
    """
    manager = await get_permission_manager()

    try:
        tool_permission = manager.get_tool_permission(request.tool_name)

        if tool_permission is None:
            return {
                "allowed": False,
                "tool_name": request.tool_name,
                "tool_permission": None,
                "max_permission": request.max_permission.value,
                "reason": "Tool not registered",
            }

        if request.tool_name in manager.blacklisted_tools:
            return {
                "allowed": False,
                "tool_name": request.tool_name,
                "tool_permission": tool_permission.value,
                "max_permission": request.max_permission.value,
                "reason": "Tool is blacklisted",
            }

        allowed = manager.is_tool_allowed(request.tool_name, request.max_permission)

        return {
            "allowed": allowed,
            "tool_name": request.tool_name,
            "tool_permission": tool_permission.value,
            "max_permission": request.max_permission.value,
            "reason": None
            if allowed
            else f"Tool permission '{tool_permission.value}' exceeds max '{request.max_permission.value}'",
        }

    except Exception as e:
        logger.error(f"Failed to check permission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blacklist/{tool_name}")
async def blacklist_tool(tool_name: str):
    """
    将工具加入黑名单

    被加入黑名单的工具将无法使用，无论其权限级别。

    参数:
    - **tool_name**: 工具名称

    用途:
    - 临时禁用有问题的工具
    - 应急安全措施
    """
    manager = await get_permission_manager()

    try:
        manager.blacklist_tool(tool_name)

        return {
            "success": True,
            "tool_name": tool_name,
            "action": "blacklisted",
        }

    except Exception as e:
        logger.error(f"Failed to blacklist tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blacklist/{tool_name}")
async def whitelist_tool(tool_name: str):
    """
    将工具移出黑名单

    恢复被黑名单的工具。

    参数:
    - **tool_name**: 工具名称
    """
    manager = await get_permission_manager()

    try:
        manager.whitelist_tool(tool_name)

        return {
            "success": True,
            "tool_name": tool_name,
            "action": "whitelisted",
        }

    except Exception as e:
        logger.error(f"Failed to whitelist tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/{permission_level}")
async def get_tools_by_permission(permission_level: ToolPermissionLevel):
    """
    获取指定权限级别的工具

    参数:
    - **permission_level**: 权限级别

    返回:
    - tools: 工具名称列表
    - total: 工具数量
    """
    manager = await get_permission_manager()

    try:
        tools = manager.get_tools_by_permission(permission_level)

        return {
            "permission_level": permission_level.value,
            "tools": tools,
            "total": len(tools),
        }

    except Exception as e:
        logger.error(f"Failed to get tools by permission: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_permission_summary():
    """
    获取权限统计摘要

    返回:
    - total_tools: 总工具数
    - blacklisted_tools: 黑名单工具数
    - permission_distribution: 各权限级别的工具分布
    """
    manager = await get_permission_manager()

    try:
        summary = manager.get_permission_summary()

        return summary

    except Exception as e:
        logger.error(f"Failed to get permission summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/levels")
async def list_permission_levels():
    """
    列出所有权限级别

    返回:
    - levels: 权限级别列表及说明
    """
    return {
        "levels": [
            {
                "name": ToolPermissionLevel.LOW_RISK.value,
                "description": "只读操作，无副作用",
                "examples": ["web_search", "calculator", "knowledge_query"],
            },
            {
                "name": ToolPermissionLevel.MODERATE_RISK.value,
                "description": "有限的写操作",
                "examples": ["send_email", "create_note", "update_calendar"],
            },
            {
                "name": ToolPermissionLevel.HIGH_RISK.value,
                "description": "重要的写操作或外部调用",
                "examples": ["file_write", "api_call", "code_executor"],
            },
            {
                "name": ToolPermissionLevel.CRITICAL.value,
                "description": "数据修改、删除操作",
                "examples": ["file_delete", "database_update", "user_data_modify"],
            },
            {
                "name": ToolPermissionLevel.DANGEROUS.value,
                "description": "系统级操作、不可逆操作",
                "examples": ["system_command", "shell_executor", "database_drop"],
            },
        ],
        "total": 5,
    }
