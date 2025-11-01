"""
Connection Manager - WebSocket 连接管理器

管理所有活跃的 WebSocket 连接
"""

import logging
import time

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        """初始化连接管理器"""
        # 活跃连接: {connection_id: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}

        # 连接元数据: {connection_id: metadata}
        self.connection_metadata: dict[str, dict] = {}

        # 统计信息
        self.total_connections = 0
        self.total_messages = 0

    async def connect(self, websocket: WebSocket, connection_id: str, metadata: dict | None = None):
        """
        接受新连接

        Args:
            websocket: WebSocket 实例
            connection_id: 连接 ID
            metadata: 连接元数据（可选）
        """
        await websocket.accept()

        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": time.time(),
            "metadata": metadata or {},
            "message_count": 0,
        }

        self.total_connections += 1

        logger.info(f"WebSocket connected: {connection_id}, active={len(self.active_connections)}")

    def disconnect(self, connection_id: str):
        """
        断开连接

        Args:
            connection_id: 连接 ID
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]

        logger.info(
            f"WebSocket disconnected: {connection_id}, active={len(self.active_connections)}"
        )

    async def send_message(self, connection_id: str, message: dict):
        """
        发送消息到指定连接

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)

                # 更新统计
                self.total_messages += 1
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id]["message_count"] += 1

            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                self.disconnect(connection_id)

    async def send_text(self, connection_id: str, text: str):
        """
        发送文本消息到指定连接

        Args:
            connection_id: 连接 ID
            text: 文本内容
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_text(text)

                # 更新统计
                self.total_messages += 1
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id]["message_count"] += 1

            except Exception as e:
                logger.error(f"Failed to send text to {connection_id}: {e}")
                self.disconnect(connection_id)

    async def broadcast(self, message: dict, exclude: list[str] | None = None):
        """
        广播消息到所有连接

        Args:
            message: 消息内容
            exclude: 排除的连接 ID 列表
        """
        exclude = exclude or []

        for connection_id in list(self.active_connections.keys()):
            if connection_id not in exclude:
                await self.send_message(connection_id, message)

    def get_connection(self, connection_id: str) -> WebSocket | None:
        """
        获取连接

        Args:
            connection_id: 连接 ID

        Returns:
            WebSocket 实例或 None
        """
        return self.active_connections.get(connection_id)

    def get_metadata(self, connection_id: str) -> dict | None:
        """
        获取连接元数据

        Args:
            connection_id: 连接 ID

        Returns:
            元数据字典或 None
        """
        return self.connection_metadata.get(connection_id)

    def get_statistics(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "total_messages": self.total_messages,
            "connections": [
                {
                    "id": conn_id,
                    "connected_at": meta["connected_at"],
                    "message_count": meta["message_count"],
                    "uptime": time.time() - meta["connected_at"],
                }
                for conn_id, meta in self.connection_metadata.items()
            ],
        }


# 全局连接管理器实例
_connection_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """
    获取连接管理器实例（单例）

    Returns:
        ConnectionManager 实例
    """
    global _connection_manager

    if _connection_manager is None:
        _connection_manager = ConnectionManager()

    return _connection_manager
