"""
WebSocket Router - WebSocket API 路由
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.connection_manager import get_connection_manager
from app.websocket.message_handler import get_message_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    """
    Agent WebSocket 端点

    支持实时 Agent 交互
    """
    # 生成连接 ID
    connection_id = str(uuid.uuid4())

    # 获取管理器和处理器
    connection_manager = get_connection_manager()
    message_handler = get_message_handler()

    try:
        # 接受连接
        await connection_manager.connect(
            websocket,
            connection_id,
            metadata={"type": "agent"}
        )

        # 发送欢迎消息
        await connection_manager.send_message(
            connection_id,
            {
                "type": "connected",
                "connection_id": connection_id,
                "message": "Connected to Agent WebSocket",
            },
        )

        # 接收消息循环
        while True:
            # 接收消息
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # 处理消息
                await message_handler.handle_message(connection_id, message)

            except json.JSONDecodeError:
                await connection_manager.send_message(
                    connection_id,
                    {
                        "type": "error",
                        "error": "Invalid JSON format",
                    },
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
        connection_manager.disconnect(connection_id)

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(connection_id)


@router.get("/statistics", summary="获取 WebSocket 统计信息")
async def get_statistics():
    """
    获取 WebSocket 连接统计信息

    Returns:
        统计信息
    """
    connection_manager = get_connection_manager()
    return connection_manager.get_statistics()
