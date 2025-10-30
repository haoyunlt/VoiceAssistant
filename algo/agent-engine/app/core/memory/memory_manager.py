"""
Memory Manager - 记忆管理器
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器"""

    def __init__(self) -> None:
        # 简化实现：使用内存字典
        # 实际应该使用 Redis 或数据库
        self.memory_store: dict[str, dict[str, Any]] = {}
        logger.info("Memory manager created")

    async def initialize(self) -> None:
        """初始化"""
        logger.info("Memory manager initialized")

    async def get_memory(self, conversation_id: str) -> dict[str, Any]:
        """获取记忆"""
        return self.memory_store.get(conversation_id, {"history": [], "summary": ""})

    async def add_to_memory(self, conversation_id: str, task: str, result: dict) -> None:
        """添加到记忆"""
        if conversation_id not in self.memory_store:
            self.memory_store[conversation_id] = {"history": [], "summary": ""}

        self.memory_store[conversation_id]["history"].append(
            {
                "task": task,
                "result": result,
            }
        )

        # 保留最近10条
        self.memory_store[conversation_id]["history"] = self.memory_store[conversation_id][
            "history"
        ][-10:]

    async def clear_memory(self, conversation_id: str) -> None:
        """清除记忆"""
        if conversation_id in self.memory_store:
            del self.memory_store[conversation_id]

    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Memory manager cleaned up")
