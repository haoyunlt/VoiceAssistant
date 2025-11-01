"""
Message Handler - WebSocket 消息处理器

处理不同类型的 WebSocket 消息
"""

import logging
import time
from typing import Any

from app.llm.multi_llm_adapter import get_multi_llm_adapter
from app.tools.dynamic_registry import get_tool_registry
from app.websocket.connection_manager import get_connection_manager

logger = logging.getLogger(__name__)


class MessageHandler:
    """WebSocket 消息处理器"""

    def __init__(self):
        """初始化消息处理器"""
        self.connection_manager = get_connection_manager()
        self.llm_adapter = get_multi_llm_adapter()
        self.tool_registry = get_tool_registry()

    async def handle_message(self, connection_id: str, message: dict[str, Any]) -> None:
        """
        处理收到的消息

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        message_type = message.get("type")

        logger.info(f"Handling message type: {message_type} from {connection_id}")

        try:
            if message_type == "ping":
                await self._handle_ping(connection_id, message)

            elif message_type == "agent_query":
                await self._handle_agent_query(connection_id, message)

            elif message_type == "streaming_query":
                await self._handle_streaming_query(connection_id, message)

            elif message_type == "tool_call":
                await self._handle_tool_call(connection_id, message)

            elif message_type == "cancel":
                await self._handle_cancel(connection_id, message)

            else:
                await self._send_error(connection_id, f"Unknown message type: {message_type}")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self._send_error(connection_id, str(e))

    async def _handle_ping(self, connection_id: str, _message: dict) -> None:
        """
        处理 ping 消息

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        await self.connection_manager.send_message(
            connection_id,
            {
                "type": "pong",
                "timestamp": time.time(),
            },
        )

    async def _handle_agent_query(self, connection_id: str, message: dict) -> None:
        """
        处理 Agent 查询（非流式）

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        query = message.get("query", "")
        if not query:
            await self._send_error(connection_id, "Query is required")
            return

        # 发送处理中消息
        await self.connection_manager.send_message(
            connection_id,
            {
                "type": "status",
                "status": "processing",
                "timestamp": time.time(),
            },
        )

        try:
            # 调用 LLM
            messages = [{"role": "user", "content": query}]
            response = await self.llm_adapter.chat(messages=messages)

            # 发送响应
            await self.connection_manager.send_message(
                connection_id,
                {
                    "type": "agent_response",
                    "content": response.get("content", ""),
                    "vendor": response.get("vendor", "unknown"),
                    "timestamp": time.time(),
                },
            )

        except Exception as e:
            logger.error(f"Agent query failed: {e}")
            await self._send_error(connection_id, f"Query failed: {str(e)}")

    async def _handle_streaming_query(self, connection_id: str, message: dict) -> None:
        """
        处理流式查询

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        query = message.get("query", "")
        if not query:
            await self._send_error(connection_id, "Query is required")
            return

        # 发送开始消息
        await self.connection_manager.send_message(
            connection_id,
            {
                "type": "stream_start",
                "timestamp": time.time(),
            },
        )

        try:
            # 流式调用 LLM
            messages = [{"role": "user", "content": query}]

            async for chunk in self.llm_adapter.chat_stream(messages=messages):
                content = chunk.get("content", "")

                if content:
                    # 发送流式内容
                    await self.connection_manager.send_message(
                        connection_id,
                        {
                            "type": "stream_chunk",
                            "content": content,
                            "timestamp": time.time(),
                        },
                    )

            # 发送结束消息
            await self.connection_manager.send_message(
                connection_id,
                {
                    "type": "stream_end",
                    "timestamp": time.time(),
                },
            )

        except Exception as e:
            logger.error(f"Streaming query failed: {e}")
            await self._send_error(connection_id, f"Streaming failed: {str(e)}")

    async def _handle_tool_call(self, connection_id: str, message: dict) -> None:
        """
        处理工具调用

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        tool_name = message.get("tool_name")
        tool_params = message.get("params", {})

        if not tool_name:
            await self._send_error(connection_id, "Tool name is required")
            return

        try:
            # 获取工具
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                await self._send_error(connection_id, f"Tool not found: {tool_name}")
                return

            # 执行工具
            result = await tool.execute(**tool_params)

            # 发送结果
            await self.connection_manager.send_message(
                connection_id,
                {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": result,
                    "timestamp": time.time(),
                },
            )

        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            await self._send_error(connection_id, f"Tool call failed: {str(e)}")

    async def _handle_cancel(self, connection_id: str, _message: dict) -> None:
        """
        处理取消请求

        Args:
            connection_id: 连接 ID
            message: 消息内容
        """
        # TODO: 实现任务取消逻辑
        await self.connection_manager.send_message(
            connection_id,
            {
                "type": "cancelled",
                "timestamp": time.time(),
            },
        )

    async def _send_error(self, connection_id: str, error: str) -> None:
        """
        发送错误消息

        Args:
            connection_id: 连接 ID
            error: 错误信息
        """
        await self.connection_manager.send_message(
            connection_id,
            {
                "type": "error",
                "error": error,
                "timestamp": time.time(),
            },
        )


# 全局消息处理器实例
_message_handler: MessageHandler | None = None


def get_message_handler() -> MessageHandler:
    """
    获取消息处理器实例（单例）

    Returns:
        MessageHandler 实例
    """
    global _message_handler

    if _message_handler is None:
        _message_handler = MessageHandler()

    return _message_handler
