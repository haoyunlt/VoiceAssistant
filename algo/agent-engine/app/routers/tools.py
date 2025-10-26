"""工具管理路由"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from app.services.tool_service import ToolService

router = APIRouter()
logger = logging.getLogger(__name__)

# 创建工具服务实例
tool_service = ToolService()


@router.get("/list")
async def list_tools() -> List[Dict[str, Any]]:
    """列出所有可用工具"""
    tools = tool_service.list_tools()
    return tools


@router.get("/{tool_name}")
async def get_tool_info(tool_name: str) -> Dict[str, Any]:
    """获取工具详细信息"""
    tool_info = tool_service.get_tool_info(tool_name)
    if not tool_info:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return tool_info


@router.post("/{tool_name}/execute")
async def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    直接执行指定工具

    用于测试工具或直接调用
    """
    try:
        result = await tool_service.execute_tool(tool_name, parameters)
        return {
            "tool": tool_name,
            "result": result,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "tool": tool_name,
            "error": str(e),
            "status": "failed",
        }
