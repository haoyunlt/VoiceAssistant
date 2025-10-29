"""
记忆管理器
管理 Agent 的短期和长期记忆
"""

import json
import logging
from typing import Any

from langchain.schema import (  # type: ignore[import]
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from redis import Redis  # type: ignore[import]

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器"""

    def __init__(
        self,
        redis_client: Redis | None = None,
        max_short_term_messages: int = 20,
        short_term_ttl: int = 3600,  # 1 hour
        long_term_ttl: int = 86400 * 7,  # 7 days
    ) -> None:
        """
        初始化记忆管理器

        Args:
            redis_client: Redis 客户端（可选）
            max_short_term_messages: 短期记忆最大消息数
            short_term_ttl: 短期记忆 TTL（秒）
            long_term_ttl: 长期记忆 TTL（秒）
        """
        self.redis_client = redis_client
        self.max_short_term_messages = max_short_term_messages
        self.short_term_ttl = short_term_ttl
        self.long_term_ttl = long_term_ttl

        # 内存存储（如果没有 Redis）
        self.memory_store: dict[str, list[BaseMessage]] = {}  # type: ignore
        self.metadata_store: dict[str, dict[str, Any]] = {}

        logger.info("Memory manager initialized")

    def save_memory(
        self,
        conversation_id: str,
        messages: list[BaseMessage],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        保存记忆

        Args:
            conversation_id: 对话 ID
            messages: 消息列表
            metadata: 元数据
        """
        # 截断消息（只保留最近的 N 条）
        truncated_messages = messages[-self.max_short_term_messages :]

        if self.redis_client:
            # 存储到 Redis
            key = f"memory:conversation:{conversation_id}"

            # 序列化消息
            serialized = self._serialize_messages(truncated_messages)

            # 保存
            self.redis_client.setex(key, self.short_term_ttl, json.dumps(serialized))

            # 保存元数据
            if metadata:
                meta_key = f"memory:metadata:{conversation_id}"
                self.redis_client.setex(meta_key, self.short_term_ttl, json.dumps(metadata))

            logger.debug(
                f"Saved memory to Redis: {conversation_id}, {len(truncated_messages)} messages"
            )
        else:
            # 存储到内存
            self.memory_store[conversation_id] = truncated_messages
            if metadata:
                self.metadata_store[conversation_id] = metadata

            logger.debug(
                f"Saved memory to local store: {conversation_id}, {len(truncated_messages)} messages"
            )

    def load_memory(self, conversation_id: str) -> list[BaseMessage]:
        """
        加载记忆

        Args:
            conversation_id: 对话 ID

        Returns:
            消息列表，不存在返回空列表
        """
        if self.redis_client:
            # 从 Redis 加载
            key = f"memory:conversation:{conversation_id}"
            data = self.redis_client.get(key)

            if data:
                serialized = json.loads(data)
                messages = self._deserialize_messages(serialized)
                logger.debug(
                    f"Loaded memory from Redis: {conversation_id}, {len(messages)} messages"
                )
                return messages

            return []
        else:
            # 从内存加载
            messages_or_none = self.memory_store.get(conversation_id)
            if messages_or_none:
                logger.debug(
                    f"Loaded memory from local store: {conversation_id}, {len(messages_or_none)} messages"
                )
                return messages_or_none
            return []

    def delete_memory(self, conversation_id: str) -> None:
        """
        删除记忆

        Args:
            conversation_id: 对话 ID
        """
        if self.redis_client:
            key = f"memory:conversation:{conversation_id}"
            meta_key = f"memory:metadata:{conversation_id}"

            self.redis_client.delete(key)
            self.redis_client.delete(meta_key)

            logger.info(f"Deleted memory from Redis: {conversation_id}")
        else:
            if conversation_id in self.memory_store:
                del self.memory_store[conversation_id]
            if conversation_id in self.metadata_store:
                del self.metadata_store[conversation_id]

            logger.info(f"Deleted memory from local store: {conversation_id}")

    def summarize_conversation(self, messages: list[BaseMessage], llm: Any | None = None) -> str:  # type: ignore
        """
        总结对话

        Args:
            messages: 消息列表
            llm: LLM 实例（可选）

        Returns:
            对话摘要
        """
        if not llm:
            # 简单摘要：只返回消息数量
            return f"Conversation with {len(messages)} messages"

        # 构造摘要提示
        conversation_text = "\n".join(
            [f"{msg.__class__.__name__}: {msg.content}" for msg in messages]
        )

        prompt = f"""Please summarize the following conversation:

{conversation_text}

Summary:"""

        # 调用 LLM 生成摘要
        response = llm.invoke(prompt)
        return response.content  # type: ignore

    def get_relevant_memory(
        self,
        conversation_id: str,
        query: str,
        top_k: int = 5,  # noqa: ARG002 - reserved for vector search
    ) -> list[BaseMessage]:  # type: ignore
        """
        获取相关记忆

        Args:
            conversation_id: 对话 ID
            query: 查询
            top_k: 返回数量

        Returns:
            相关消息列表
        """
        # 记录查询以便未来扩展
        _ = query

        # 加载所有记忆
        all_messages = self.load_memory(conversation_id)  # type: ignore

        if not all_messages:
            return []

        # 简化版：返回最近的 top_k 条消息
        # TODO: 实现基于向量相似度的检索
        return all_messages[-top_k:]

    def _serialize_messages(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        """序列化消息"""
        serialized = []
        for msg in messages:
            serialized.append(
                {
                    "type": msg.__class__.__name__,
                    "content": msg.content,
                    "additional_kwargs": getattr(msg, "additional_kwargs", {}),
                }
            )
        return serialized

    def _deserialize_messages(self, serialized: list[dict[str, Any]]) -> list[BaseMessage]:
        """反序列化消息"""
        messages = []
        for item in serialized:
            msg_type = item["type"]
            content = item["content"]

            if msg_type == "HumanMessage":
                messages.append(HumanMessage(content=content))
            elif msg_type == "AIMessage":
                messages.append(AIMessage(content=content))
            elif msg_type == "SystemMessage":
                messages.append(SystemMessage(content=content))
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        return messages


class LongTermMemory:
    """长期记忆（基于向量数据库）"""

    def __init__(
        self, vector_store_client: Any | None = None, collection_name: str = "agent_memory"
    ):
        """
        初始化长期记忆

        Args:
            vector_store_client: 向量数据库客户端
            collection_name: 集合名称
        """
        self.vector_store = vector_store_client
        self.collection_name = collection_name

        logger.info("Long-term memory initialized")

    def save_important_message(
        self,
        conversation_id: str,
        message: str,  # noqa: ARG002 - reserved for vector storage
        embedding: list[float],  # noqa: ARG002 - reserved for vector storage
        metadata: dict[str, Any] | None = None,  # noqa: ARG002 - reserved for vector storage
    ) -> None:
        """
        保存重要消息到长期记忆

        Args:
            conversation_id: 对话 ID
            message: 消息内容
            embedding: 向量
            metadata: 元数据
        """
        if not self.vector_store:
            logger.warning("Vector store not configured, cannot save to long-term memory")
            return

        # TODO: Implement the actual vector storage logic here
        logger.info(f"Saving message to long-term memory: {conversation_id}")

    def retrieve_relevant_memories(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,  # noqa: ARG002 - reserved for vector search
    ) -> list[dict[str, Any]]:
        """
        检索相关记忆

        Args:
            query_embedding: 查询向量
            top_k: 返回数量
            filters: 过滤条件

        Returns:
            相关记忆列表
        """
        _ = (query_embedding, filters)

        if not self.vector_store:
            logger.warning("Vector store not configured, cannot retrieve from long-term memory")
            return []

        # TODO: 实现向量检索
        logger.info(f"Retrieving memories from long-term memory: top_k={top_k}")
        return []
