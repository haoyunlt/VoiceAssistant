"""
统一记忆管理器

整合短期记忆和长期记忆，提供统一的接口
"""

from typing import Any, Dict, List, Optional

import logging
from app.memory.memory_manager import MemoryManager as ShortTermMemory
from app.memory.vector_memory_manager import VectorMemoryManager

logger = logging.getLogger(__name__)


class UnifiedMemoryManager:
    """统一记忆管理器"""

    def __init__(
        self,
        # 短期记忆配置
        redis_client=None,
        max_short_term_messages: int = 20,
        short_term_ttl: int = 3600,
        # 长期记忆配置
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        embedding_service_url: str = "http://localhost:8002",
        collection_name: str = "agent_memory",
        time_decay_half_life_days: int = 30,
        # 自动存储策略
        auto_save_to_long_term: bool = True,
        long_term_importance_threshold: float = 0.6,
    ):
        """
        初始化统一记忆管理器

        Args:
            redis_client: Redis 客户端
            max_short_term_messages: 短期记忆最大消息数
            short_term_ttl: 短期记忆 TTL
            milvus_host: Milvus 主机
            milvus_port: Milvus 端口
            embedding_service_url: Embedding 服务 URL
            collection_name: Milvus collection 名称
            time_decay_half_life_days: 时间衰减半衰期（天）
            auto_save_to_long_term: 是否自动保存重要记忆到长期记忆
            long_term_importance_threshold: 长期记忆重要性阈值
        """
        # 短期记忆
        self.short_term = ShortTermMemory(
            redis_client=redis_client,
            max_short_term_messages=max_short_term_messages,
            short_term_ttl=short_term_ttl,
        )

        # 长期记忆
        self.long_term = VectorMemoryManager(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_service_url=embedding_service_url,
            collection_name=collection_name,
            time_decay_half_life_days=time_decay_half_life_days,
        )

        # 配置
        self.auto_save_to_long_term = auto_save_to_long_term
        self.long_term_importance_threshold = long_term_importance_threshold

        logger.info(
            "UnifiedMemoryManager initialized: "
            f"auto_save={auto_save_to_long_term}, "
            f"threshold={long_term_importance_threshold}"
        )

    async def add_memory(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        role: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        添加记忆（自动分配到短期或长期）

        Args:
            user_id: 用户 ID
            conversation_id: 对话 ID
            content: 内容
            role: 角色 (user/assistant/system)
            metadata: 元数据

        Returns:
            memory_id: 如果保存到长期记忆，返回 memory_id
        """
        # 1. 保存到短期记忆 (对话级)
        # TODO: 需要先加载现有消息，然后追加
        logger.debug(
            f"Adding to short-term memory: conversation_id={conversation_id}, "
            f"role={role}"
        )

        # 2. 评估是否保存到长期记忆
        if self.auto_save_to_long_term:
            importance = await self.long_term._evaluate_importance(content, metadata)

            if importance >= self.long_term_importance_threshold:
                # 保存到长期记忆
                memory_id = await self.long_term.store_memory(
                    user_id=user_id,
                    content=content,
                    memory_type=role,
                    importance=importance,
                    auto_evaluate_importance=False,  # 已经评估过了
                )

                logger.info(
                    f"Saved to long-term memory: memory_id={memory_id}, "
                    f"importance={importance:.2f}"
                )

                return memory_id

        return None

    async def recall_memories(
        self,
        user_id: str,
        query: str,
        conversation_id: Optional[str] = None,
        top_k: int = 5,
        include_short_term: bool = True,
        include_long_term: bool = True,
    ) -> Dict[str, Any]:
        """
        回忆相关记忆（短期+长期）

        Args:
            user_id: 用户 ID
            query: 查询内容
            conversation_id: 对话 ID（用于短期记忆）
            top_k: 返回数量
            include_short_term: 是否包含短期记忆
            include_long_term: 是否包含长期记忆

        Returns:
            {
                "short_term": [...],  # 短期记忆
                "long_term": [...],   # 长期记忆
                "combined": [...]     # 融合后的记忆
            }
        """
        result = {"short_term": [], "long_term": [], "combined": []}

        # 1. 短期记忆 (对话级)
        if include_short_term and conversation_id:
            short_term_memories = self.short_term.get_relevant_memory(
                conversation_id=conversation_id, query=query, top_k=top_k
            )

            # 转换为统一格式
            for msg in short_term_memories:
                result["short_term"].append(
                    {
                        "type": "short_term",
                        "content": msg.content,
                        "role": msg.__class__.__name__.replace("Message", "").lower(),
                        "score": 1.0,  # 短期记忆默认高分
                    }
                )

        # 2. 长期记忆 (向量检索)
        if include_long_term:
            long_term_memories = await self.long_term.retrieve_memory(
                user_id=user_id, query=query, top_k=top_k
            )

            for mem in long_term_memories:
                result["long_term"].append(
                    {
                        "type": "long_term",
                        "memory_id": mem["memory_id"],
                        "content": mem["content"],
                        "memory_type": mem["memory_type"],
                        "importance": mem["importance"],
                        "score": mem["score"],
                        "days_ago": mem["days_ago"],
                        "access_count": mem["access_count"],
                    }
                )

        # 3. 融合记忆 (按分数排序)
        all_memories = result["short_term"] + result["long_term"]
        all_memories.sort(key=lambda x: x["score"], reverse=True)
        result["combined"] = all_memories[: top_k * 2]  # 返回更多融合结果

        logger.info(
            f"Recalled memories: short_term={len(result['short_term'])}, "
            f"long_term={len(result['long_term'])}, "
            f"combined={len(result['combined'])}"
        )

        return result

    async def store_important_memory(
        self,
        user_id: str,
        content: str,
        memory_type: str = "important",
        importance: Optional[float] = None,
    ) -> str:
        """
        直接存储重要记忆到长期记忆

        Args:
            user_id: 用户 ID
            content: 内容
            memory_type: 记忆类型
            importance: 重要性 (可选)

        Returns:
            memory_id: 记忆 ID
        """
        memory_id = await self.long_term.store_memory(
            user_id=user_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
        )

        logger.info(
            f"Stored important memory: user_id={user_id}, memory_id={memory_id}"
        )

        return memory_id

    async def delete_memory(self, memory_id: str):
        """
        删除长期记忆

        Args:
            memory_id: 记忆 ID
        """
        await self.long_term.delete_memory(memory_id)

        logger.info(f"Deleted memory: {memory_id}")

    async def list_user_memories(
        self, user_id: str, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出用户的所有长期记忆

        Args:
            user_id: 用户 ID
            limit: 返回数量
            offset: 偏移量

        Returns:
            记忆列表
        """
        memories = await self.long_term.list_user_memories(
            user_id=user_id, limit=limit, offset=offset
        )

        logger.info(f"Listed {len(memories)} memories for user {user_id}")

        return memories

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息
        """
        return {
            "short_term": {
                "type": "redis/memory",
                "max_messages": self.short_term.max_short_term_messages,
                "ttl": self.short_term.short_term_ttl,
            },
            "long_term": self.long_term.get_stats(),
            "config": {
                "auto_save_to_long_term": self.auto_save_to_long_term,
                "importance_threshold": self.long_term_importance_threshold,
            },
        }

