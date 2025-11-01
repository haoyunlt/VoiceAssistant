"""
工具管理路由

提供工具列表、执行、注册等 API
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException  # type: ignore[import]
from pydantic import BaseModel, Field  # type: ignore[import]

from app.tools.dynamic_registry import get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])


# === Request/Response Models ===


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""

    tool_name: str = Field(..., description="工具名称")
    parameters: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolExecuteResponse(BaseModel):
    """工具执行响应"""

    tool_name: str = Field(..., description="工具名称")
    result: str = Field(..., description="执行结果")
    execution_time_ms: float = Field(..., description="执行时间（毫秒）")
    success: bool = Field(..., description="是否成功")


class ToolListResponse(BaseModel):
    """工具列表响应"""

    tools: list = Field(..., description="工具列表")
    count: int = Field(..., description="工具数量")


# === API Endpoints ===


@router.get("/list", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """
    列出所有可用工具

    Returns:
        工具列表
    """
    try:
        tool_registry = get_tool_registry()
        tools = tool_registry.list_tools()  # type: ignore

        return ToolListResponse(tools=tools, count=len(tools))

    except Exception as e:
        logger.error(f"Failed to list tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/names")
async def list_tool_names() -> dict[str, Any]:
    """
    列出所有工具名称

    Returns:
        工具名称列表
    """
    try:
        tool_registry = get_tool_registry()
        names = tool_registry.get_tool_names()  # type: ignore

        return {"tool_names": names, "count": len(names)}

    except Exception as e:
        logger.error(f"Failed to list tool names: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/description")
async def get_tools_description() -> dict[str, Any]:
    """
    获取所有工具的文本描述

    Returns:
        工具描述文本
    """
    try:
        tool_registry = get_tool_registry()
        description = tool_registry.get_tools_description()  # type: ignore

        return {"description": description}

    except Exception as e:
        logger.error(f"Failed to get tools description: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/definitions")
async def get_tool_definitions_for_llm() -> dict[str, Any]:
    """
    获取 OpenAI Function Calling 格式的工具定义

    Returns:
        函数定义列表
    """
    try:
        tool_registry = get_tool_registry()
        definitions = tool_registry.get_tool_definitions_for_llm()  # type: ignore

        return {"definitions": definitions, "count": len(definitions)}

    except Exception as e:
        logger.error(f"Failed to get tool definitions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{tool_name}")
async def get_tool_info(tool_name: str) -> dict[str, Any]:
    """
    获取指定工具的信息

    Args:
        tool_name: 工具名称

    Returns:
        工具定义
    """
    try:
        tool_registry = get_tool_registry()
        tool_info = tool_registry.get_tool_info(tool_name)

        if not tool_info:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
    """
    执行工具

    Args:
        request: 工具执行请求

    Returns:
        执行结果
    """
    start_time = time.time()

    try:
        tool_registry = get_tool_registry()

        # 执行工具
        result = await tool_registry.execute_tool(
            tool_name=request.tool_name, parameters=request.parameters
        )

        execution_time = (time.time() - start_time) * 1000

        return ToolExecuteResponse(
            tool_name=request.tool_name,
            result=result,
            execution_time_ms=execution_time,
            success=True,
        )

    except ValueError as e:
        # 工具不存在
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000

        logger.error(f"Tool '{request.tool_name}' execution failed: {e}", exc_info=True)

        # 返回失败信息（不抛出异常）
        return ToolExecuteResponse(
            tool_name=request.tool_name,
            result=f"执行失败: {str(e)}",
            execution_time_ms=execution_time,
            success=False,
        )


@router.post("/reload")
async def reload_builtin_tools() -> dict[str, Any]:
    """
    重新加载内置工具

    Returns:
        成功消息
    """
    try:
        tool_registry = get_tool_registry()
        tool_registry.reload_builtin_tools()

        return {
            "message": "Builtin tools reloaded successfully",
            "count": len(tool_registry.get_tool_names()),  # type: ignore
        }

    except Exception as e:
        logger.error(f"Failed to reload builtin tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
