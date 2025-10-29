"""
Memory Manager - 记忆管理器
"""

import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器"""

    def __init__(self):
        # 简化实现：使用内存字典
        # 实际应该使用 Redis 或数据库
        self.memory_store = {}
        logger.info("Memory manager created")

    async def initialize(self):
        """初始化"""
        logger.info("Memory manager initialized")

    async def get_memory(self, conversation_id: str) -> dict:
        """获取记忆"""
        return self.memory_store.get(conversation_id, {"history": [], "summary": ""})

    async def add_to_memory(self, conversation_id: str, task: str, result: dict):
        """添加到记忆"""
        if conversation_id not in self.memory_store:
            self.memory_store[conversation_id] = {"history": [], "summary": ""}

        self.memory_store[conversation_id]["history"].append({
            "task": task,
            "result": result,
        })

        # 保留最近10条
        self.memory_store[conversation_id]["history"] = self.memory_store[conversation_id]["history"][-10:]

    async def clear_memory(self, conversation_id: str):
        """清除记忆"""
        if conversation_id in self.memory_store:
            del self.memory_store[conversation_id]

    async def cleanup(self):
        """清理资源"""
        logger.info("Memory manager cleaned up")
