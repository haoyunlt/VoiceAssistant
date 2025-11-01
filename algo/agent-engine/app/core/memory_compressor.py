"""
记忆压缩模块

压缩长时对话历史，提取关键信息，减少存储和检索开销。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemorySummary:
    """记忆摘要"""

    conversation_id: str
    summary: str  # 摘要内容
    key_points: list[str]  # 关键要点
    entities: list[dict[str, str]]  # 提取的实体
    original_message_count: int  # 原始消息数
    compressed_ratio: float  # 压缩比例
    created_at: datetime


class MemoryCompressor:
    """
    记忆压缩器

    将长对话历史压缩为精简的摘要，保留关键信息。

    用法:
        compressor = MemoryCompressor(llm_client, memory_manager)

        # 压缩会话记忆
        summary = await compressor.compress_conversation(
            conversation_id="conv_123",
            threshold=20  # 超过20条消息时压缩
        )

        # 获取压缩后的记忆用于上下文
        context = await compressor.get_compressed_context("conv_123")
    """

    def __init__(
        self,
        llm_client: Any,
        memory_manager: Any,
        model: str = "gpt-3.5-turbo",
        compression_threshold: int = 20,
        keep_recent_messages: int = 5,
    ):
        """
        初始化记忆压缩器

        Args:
            llm_client: LLM 客户端
            memory_manager: 记忆管理器
            model: 使用的模型（建议用便宜的模型）
            compression_threshold: 触发压缩的消息数阈值
            keep_recent_messages: 保留的最近消息数（不压缩）
        """
        self.llm_client = llm_client
        self.memory_manager = memory_manager
        self.model = model
        self.compression_threshold = compression_threshold
        self.keep_recent_messages = keep_recent_messages

        # 压缩历史（内存缓存）
        self.summaries: dict[str, MemorySummary] = {}

        logger.info(
            f"MemoryCompressor initialized (threshold={compression_threshold}, "
            f"keep_recent={keep_recent_messages})"
        )

    async def compress_conversation(
        self, conversation_id: str, force: bool = False
    ) -> MemorySummary | None:
        """
        压缩会话记忆

        Args:
            conversation_id: 会话 ID
            force: 是否强制压缩（忽略阈值）

        Returns:
            记忆摘要
        """
        # 获取完整对话历史
        messages = await self.memory_manager.get_conversation_history(conversation_id)

        if not messages:
            logger.warning(f"No messages found for conversation {conversation_id}")
            return None

        # 检查是否需要压缩
        if not force and len(messages) < self.compression_threshold:
            logger.debug(
                f"Conversation {conversation_id} has {len(messages)} messages, "
                f"below threshold {self.compression_threshold}"
            )
            return None

        # 分离最近消息和历史消息
        messages[-self.keep_recent_messages :]
        historical_messages = messages[: -self.keep_recent_messages]

        if not historical_messages:
            logger.debug(f"No historical messages to compress for {conversation_id}")
            return None

        # 压缩历史消息
        summary = await self._generate_summary(conversation_id, historical_messages)

        # 缓存摘要
        self.summaries[conversation_id] = summary

        # 可选：存储到数据库或向量库
        await self._store_summary(summary)

        logger.info(
            f"Compressed {conversation_id}: {len(historical_messages)} messages → "
            f"{len(summary.summary)} chars (ratio: {summary.compressed_ratio:.2f})"
        )

        return summary

    async def _generate_summary(self, conversation_id: str, messages: list[dict]) -> MemorySummary:
        """生成对话摘要"""
        # 格式化消息
        conversation_text = self._format_messages(messages)

        prompt = f"""请总结以下对话历史，提取关键信息。

对话历史:
{conversation_text}

请以 JSON 格式输出:
{{
  "summary": "对话摘要（3-5句话）",
  "key_points": ["关键要点1", "关键要点2", ...],
  "entities": [
    {{"type": "person|org|product|...", "name": "实体名称"}},
    ...
  ]
}}

要求:
- 摘要要简洁但保留关键信息
- 提取用户的主要需求、问题、决策
- 识别重要的人物、组织、产品等实体
- 保留重要的时间节点和数字"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            result = response  # 假设返回 JSON

            # 计算压缩比
            original_length = len(conversation_text)
            compressed_length = len(result.get("summary", ""))
            compression_ratio = compressed_length / original_length if original_length > 0 else 0.0

            return MemorySummary(
                conversation_id=conversation_id,
                summary=result.get("summary", ""),
                key_points=result.get("key_points", []),
                entities=result.get("entities", []),
                original_message_count=len(messages),
                compressed_ratio=compression_ratio,
                created_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # 降级：简单截断
            return self._simple_summary(conversation_id, messages)

    def _simple_summary(self, conversation_id: str, messages: list[dict]) -> MemorySummary:
        """简单摘要（降级方案）"""
        conversation_text = self._format_messages(messages)

        # 简单截断前500个字符作为摘要
        summary = (
            conversation_text[:500] + "..." if len(conversation_text) > 500 else conversation_text
        )

        return MemorySummary(
            conversation_id=conversation_id,
            summary=summary,
            key_points=[],
            entities=[],
            original_message_count=len(messages),
            compressed_ratio=len(summary) / len(conversation_text) if conversation_text else 0.0,
            created_at=datetime.now(),
        )

    def _format_messages(self, messages: list[dict]) -> str:
        """格式化消息"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            formatted.append(f"[{timestamp}] {role}: {content}")
        return "\n".join(formatted)

    async def get_compressed_context(self, conversation_id: str) -> dict[str, Any]:
        """
        获取压缩后的上下文（用于构建 Prompt）

        Args:
            conversation_id: 会话 ID

        Returns:
            包含摘要和最近消息的字典
        """
        # 获取摘要
        summary = self.summaries.get(conversation_id)
        if not summary:
            # 尝试从存储加载
            summary = await self._load_summary(conversation_id)

        # 获取最近消息
        all_messages = await self.memory_manager.get_conversation_history(conversation_id)
        recent_messages = all_messages[-self.keep_recent_messages :] if all_messages else []

        return {
            "has_summary": summary is not None,
            "summary": summary.summary if summary else None,
            "key_points": summary.key_points if summary else [],
            "entities": summary.entities if summary else [],
            "recent_messages": recent_messages,
            "total_message_count": len(all_messages),
        }

    async def auto_compress(self, conversation_id: str) -> bool:
        """
        自动压缩（在后台定期调用）

        Args:
            conversation_id: 会话 ID

        Returns:
            是否执行了压缩
        """
        messages = await self.memory_manager.get_conversation_history(conversation_id)

        if len(messages) >= self.compression_threshold:
            summary = await self.compress_conversation(conversation_id)
            return summary is not None

        return False

    async def _store_summary(self, summary: MemorySummary):
        """存储摘要到数据库或向量库"""
        try:
            # 存储到向量库（用于语义检索）
            if hasattr(self.memory_manager, "store_summary"):
                await self.memory_manager.store_summary(
                    conversation_id=summary.conversation_id,
                    content=summary.summary,
                    metadata={
                        "key_points": summary.key_points,
                        "entities": summary.entities,
                        "original_message_count": summary.original_message_count,
                        "created_at": summary.created_at.isoformat(),
                    },
                )
            else:
                logger.warning("Memory manager does not support summary storage")

        except Exception as e:
            logger.error(f"Error storing summary: {e}")

    async def _load_summary(self, conversation_id: str) -> MemorySummary | None:
        """从存储加载摘要"""
        try:
            if hasattr(self.memory_manager, "load_summary"):
                data = await self.memory_manager.load_summary(conversation_id)
                if data:
                    return MemorySummary(
                        conversation_id=conversation_id,
                        summary=data["content"],
                        key_points=data.get("metadata", {}).get("key_points", []),
                        entities=data.get("metadata", {}).get("entities", []),
                        original_message_count=data.get("metadata", {}).get(
                            "original_message_count", 0
                        ),
                        compressed_ratio=0.0,  # 不再计算
                        created_at=datetime.fromisoformat(
                            data.get("metadata", {}).get("created_at", datetime.now().isoformat())
                        ),
                    )
            return None

        except Exception as e:
            logger.error(f"Error loading summary: {e}")
            return None

    async def get_compression_stats(self) -> dict:
        """获取压缩统计信息"""
        total_summaries = len(self.summaries)
        total_original_messages = sum(s.original_message_count for s in self.summaries.values())
        avg_compression_ratio = (
            sum(s.compressed_ratio for s in self.summaries.values()) / total_summaries
            if total_summaries > 0
            else 0.0
        )

        return {
            "total_summaries": total_summaries,
            "total_original_messages": total_original_messages,
            "avg_compression_ratio": avg_compression_ratio,
            "estimated_storage_saved_pct": (1 - avg_compression_ratio) * 100,
        }
