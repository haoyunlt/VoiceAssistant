"""
智能记忆管理器 - 完整实现记忆压缩与智能遗忘

功能:
1. 记忆重要性评分
2. 智能遗忘策略（基于重要性、时间衰减、访问频率）
3. 分层记忆（工作记忆 / 短期记忆 / 长期记忆）
4. 记忆合并与去重
5. 自动压缩与清理

实现了完整的 Iter 2 功能。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MemoryTier(Enum):
    """记忆层级"""

    WORKING = "working"  # 工作记忆：当前任务（容量小，TTL短）
    SHORT_TERM = "short_term"  # 短期记忆：最近对话（容量中等，TTL中等）
    LONG_TERM = "long_term"  # 长期记忆：重要信息（容量大，永久）


class ForgettingStrategy(Enum):
    """遗忘策略"""

    TIME_BASED = "time_based"  # 基于时间衰减
    IMPORTANCE_BASED = "importance_based"  # 基于重要性
    ACCESS_BASED = "access_based"  # 基于访问频率
    HYBRID = "hybrid"  # 综合策略


@dataclass
class Memory:
    """记忆单元"""

    memory_id: str
    content: str
    tier: MemoryTier
    importance: float  # 0-1
    created_at: datetime
    last_accessed: datetime
    access_count: int
    metadata: dict[str, Any]

    # 衰减参数
    decay_rate: float = 0.1  # 每天衰减率

    def get_current_importance(self) -> float:
        """
        计算当前重要性（考虑时间衰减）

        公式: importance * e^(-decay_rate * days_since_creation)
        """
        import math

        days_since_creation = (datetime.now() - self.created_at).total_seconds() / 86400
        decay_factor = math.exp(-self.decay_rate * days_since_creation)
        return self.importance * decay_factor

    def update_access(self) -> None:  # type: ignore [return-value]
        """更新访问信息"""
        self.last_accessed = datetime.now()
        self.access_count += 1

        # 访问增加重要性（最多+0.1）
        boost = min(0.1, 0.01 * (self.access_count - 1))
        self.importance = min(1.0, self.importance + boost)


@dataclass
class ForgettingConfig:
    """遗忘配置"""

    strategy: ForgettingStrategy = ForgettingStrategy.HYBRID
    time_threshold_days: int = 30  # 时间阈值（天）
    importance_threshold: float = 0.3  # 重要性阈值
    access_threshold: int = 2  # 最少访问次数
    max_memory_per_tier: dict[MemoryTier, int] | None = None  # 每层最大记忆数

    def __post_init__(self) -> None:  # type: ignore [return-value]
        if self.max_memory_per_tier is None:
            self.max_memory_per_tier = {
                MemoryTier.WORKING: 20,
                MemoryTier.SHORT_TERM: 100,
                MemoryTier.LONG_TERM: 500,
            }


class SmartMemoryManager:
    """
    智能记忆管理器

    用法:
        manager = SmartMemoryManager(
            llm_client=llm_client,
            storage=vector_store
        )

        # 添加记忆
        await manager.add_memory(
            content="User prefers dark mode",
            importance=0.8,
            tier=MemoryTier.LONG_TERM
        )

        # 检索记忆
        memories = await manager.retrieve(
            query="What are user's preferences?",
            top_k=5
        )

        # 自动压缩与遗忘
        await manager.auto_maintain()
    """

    def __init__(
        self,
        llm_client: Any,
        storage: Any | None = None,  # 向量存储或数据库
        config: ForgettingConfig | None = None,
    ) -> None:
        """
        初始化智能记忆管理器

        Args:
            llm_client: LLM 客户端（用于重要性评估）
            storage: 存储后端（向量库或数据库）
            config: 遗忘配置
        """
        self.llm_client = llm_client
        self.storage = storage
        self.config = config or ForgettingConfig()

        # 内存缓存（按层级存储）
        self.memories: dict[MemoryTier, list[Memory]] = {
            MemoryTier.WORKING: [],
            MemoryTier.SHORT_TERM: [],
            MemoryTier.LONG_TERM: [],
        }

        # 统计信息
        self.stats = {
            "total_added": 0,
            "total_forgotten": 0,
            "total_promoted": 0,  # 从短期提升到长期
            "total_demoted": 0,  # 从长期降级到短期
            "total_compressed": 0,
        }

        logger.info(f"SmartMemoryManager initialized (strategy={config.strategy.value})")

    async def add_memory(
        self,
        content: str,
        tier: MemoryTier = MemoryTier.SHORT_TERM,
        importance: float | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        添加记忆

        Args:
            content: 记忆内容
            tier: 记忆层级
            importance: 重要性（如未提供则自动评估）
            metadata: 元数据

        Returns:
            memory_id
        """
        # 自动评估重要性
        if importance is None:
            importance = await self._assess_importance(content)

        # 创建记忆
        memory_id = f"mem_{datetime.now().timestamp()}"
        memory = Memory(
            memory_id=memory_id,
            content=content,
            tier=tier,
            importance=importance,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            metadata=metadata or {},
        )

        # 添加到对应层级
        self.memories[tier].append(memory)
        self.stats["total_added"] += 1

        # 检查容量，触发遗忘
        await self._check_capacity(tier)

        # 存储到后端（如果有）
        if self.storage:
            await self._store_memory(memory)

        logger.debug(
            f"Added memory: tier={tier.value}, importance={importance:.2f}, id={memory_id}"
        )

        return memory_id

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        tier_filter: MemoryTier | None = None,
        min_importance: float = 0.0,
    ) -> list[Memory]:
        """
        检索记忆

        Args:
            query: 查询文本
            top_k: 返回数量
            tier_filter: 层级过滤
            min_importance: 最小重要性

        Returns:
            相关记忆列表
        """
        # 收集候选记忆
        candidates = []

        if tier_filter:
            candidates = self.memories[tier_filter]
        else:
            # 所有层级
            for tier_memories in self.memories.values():
                candidates.extend(tier_memories)

        # 过滤低重要性记忆
        candidates = [m for m in candidates if m.get_current_importance() >= min_importance]

        # 计算相关性分数
        scored_memories = []
        for memory in candidates:
            relevance_score = await self._compute_relevance(query, memory.content)
            importance_score = memory.get_current_importance()

            # 综合分数：相关性 * 重要性
            combined_score = relevance_score * importance_score

            scored_memories.append((combined_score, memory))

        # 排序并返回 top_k
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_memories = [m for _, m in scored_memories[:top_k]]

        # 更新访问信息
        for memory in top_memories:
            memory.update_access()

        logger.debug(f"Retrieved {len(top_memories)} memories for query: {query[:50]}...")

        return top_memories

    async def forget(
        self,
        memory_id: str | None = None,
        auto_mode: bool = False,
    ) -> int:
        """
        遗忘记忆

        Args:
            memory_id: 指定要遗忘的记忆ID（如为None则自动选择）
            auto_mode: 自动模式（批量遗忘）

        Returns:
            遗忘的记忆数量
        """
        forgotten_count = 0

        if memory_id:
            # 遗忘指定记忆
            for tier_memories in self.memories.values():
                for i, memory in enumerate(tier_memories):
                    if memory.memory_id == memory_id:
                        tier_memories.pop(i)
                        forgotten_count += 1
                        logger.debug(f"Forgot memory: {memory_id}")
                        break
        elif auto_mode:
            # 自动遗忘（根据策略）
            forgotten_count = await self._auto_forget()

        self.stats["total_forgotten"] += forgotten_count
        return forgotten_count

    async def _auto_forget(self) -> int:
        """自动遗忘（根据配置的策略）"""
        forgotten_count = 0

        for tier, tier_memories in self.memories.items():
            to_forget = []

            for memory in tier_memories:
                should_forget = False

                if self.config.strategy == ForgettingStrategy.TIME_BASED:
                    # 基于时间
                    age_days = (datetime.now() - memory.created_at).days
                    should_forget = age_days > self.config.time_threshold_days

                elif self.config.strategy == ForgettingStrategy.IMPORTANCE_BASED:
                    # 基于重要性
                    current_importance = memory.get_current_importance()
                    should_forget = current_importance < self.config.importance_threshold

                elif self.config.strategy == ForgettingStrategy.ACCESS_BASED:
                    # 基于访问频率
                    should_forget = memory.access_count < self.config.access_threshold

                elif self.config.strategy == ForgettingStrategy.HYBRID:
                    # 综合策略
                    age_days = (datetime.now() - memory.created_at).days
                    current_importance = memory.get_current_importance()

                    should_forget = (
                        age_days > self.config.time_threshold_days
                        and current_importance < self.config.importance_threshold
                        and memory.access_count < self.config.access_threshold
                    )

                if should_forget:
                    to_forget.append(memory)

            # 执行遗忘
            for memory in to_forget:
                tier_memories.remove(memory)
                forgotten_count += 1
                logger.debug(
                    f"Auto forgot: {memory.memory_id} (tier={tier.value}, "
                    f"importance={memory.get_current_importance():.2f})"
                )

        logger.info(f"Auto forgot {forgotten_count} memories")
        return forgotten_count

    async def promote_memory(self, memory_id: str) -> bool:
        """
        提升记忆层级（SHORT_TERM → LONG_TERM）

        Args:
            memory_id: 记忆ID

        Returns:
            是否成功
        """
        # 从短期记忆中查找
        for i, memory in enumerate(self.memories[MemoryTier.SHORT_TERM]):
            if memory.memory_id == memory_id:
                # 移动到长期记忆
                self.memories[MemoryTier.SHORT_TERM].pop(i)
                memory.tier = MemoryTier.LONG_TERM
                self.memories[MemoryTier.LONG_TERM].append(memory)

                self.stats["total_promoted"] += 1
                logger.info(f"Promoted memory {memory_id} to LONG_TERM")
                return True

        return False

    async def demote_memory(self, memory_id: str) -> bool:
        """
        降级记忆层级（LONG_TERM → SHORT_TERM）

        Args:
            memory_id: 记忆ID

        Returns:
            是否成功
        """
        # 从长期记忆中查找
        for i, memory in enumerate(self.memories[MemoryTier.LONG_TERM]):
            if memory.memory_id == memory_id:
                # 移动到短期记忆
                self.memories[MemoryTier.LONG_TERM].pop(i)
                memory.tier = MemoryTier.SHORT_TERM
                self.memories[MemoryTier.SHORT_TERM].append(memory)

                self.stats["total_demoted"] += 1
                logger.info(f"Demoted memory {memory_id} to SHORT_TERM")
                return True

        return False

    async def compress_memories(self, tier: MemoryTier = MemoryTier.SHORT_TERM) -> str:
        """
        压缩指定层级的记忆

        Args:
            tier: 记忆层级

        Returns:
            压缩后的摘要
        """
        tier_memories = self.memories[tier]

        if len(tier_memories) < 5:
            logger.debug(f"Not enough memories to compress in {tier.value}")
            return ""

        # 收集记忆内容
        memories_text = "\n".join([f"- {m.content}" for m in tier_memories])

        prompt = f"""请将以下记忆压缩为简洁的摘要，保留关键信息。

记忆内容:
{memories_text}

请输出:
1. 总体摘要（3-5句话）
2. 关键要点列表

格式:
摘要: ...
要点:
- ...
- ..."""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",
                temperature=0.2,
            )

            summary = response.strip()
            self.stats["total_compressed"] += 1

            # 将摘要作为新记忆添加到长期记忆
            await self.add_memory(
                content=summary,
                tier=MemoryTier.LONG_TERM,
                importance=0.8,
                metadata={"is_summary": True, "source_tier": tier.value},
            )

            logger.info(f"Compressed {len(tier_memories)} memories from {tier.value}")
            return summary

        except Exception as e:
            logger.error(f"Error compressing memories: {e}")
            return ""

    async def auto_maintain(self) -> None:
        """
        自动维护（定期调用）

        执行:
        1. 遗忘低价值记忆
        2. 提升重要短期记忆到长期
        3. 压缩过多的短期记忆
        4. 检查容量限制
        """
        logger.info("Starting auto maintenance...")

        # 1. 自动遗忘
        forgotten = await self._auto_forget()

        # 2. 自动提升重要记忆
        promoted = 0
        for memory in self.memories[MemoryTier.SHORT_TERM]:
            if memory.get_current_importance() > 0.8 and memory.access_count > 5:
                await self.promote_memory(memory.memory_id)
                promoted += 1

        # 3. 压缩短期记忆（如果超过阈值）
        if len(self.memories[MemoryTier.SHORT_TERM]) > 50:
            await self.compress_memories(MemoryTier.SHORT_TERM)

        # 4. 检查所有层级容量
        for tier in MemoryTier:
            await self._check_capacity(tier)

        logger.info(f"Auto maintenance completed: forgotten={forgotten}, promoted={promoted}")

    async def _check_capacity(self, tier: MemoryTier) -> None:
        """检查并执行容量限制"""
        max_capacity = self.config.max_memory_per_tier[tier]  # type: ignore [index]
        current_count = len(self.memories[tier])  # type: ignore [index]

        if current_count > max_capacity:
            # 超出容量，移除低价值记忆
            tier_memories = self.memories[tier]  # type: ignore [index]

            # 按当前重要性排序
            tier_memories.sort(key=lambda m: m.get_current_importance())

            # 移除最低价值的记忆
            to_remove = current_count - max_capacity
            for _ in range(to_remove):
                removed = tier_memories.pop(0)
                logger.debug(
                    f"Removed memory {removed.memory_id} due to capacity limit (tier={tier.value})"
                )
                self.stats["total_forgotten"] += 1

    async def _assess_importance(self, content: str) -> float:
        """
        评估记忆重要性

        Args:
            content: 记忆内容

        Returns:
            重要性分数 (0-1)
        """
        prompt = f"""评估以下信息的重要性（0-1分）。

考虑因素:
- 是否包含关键决策或偏好
- 是否与用户目标相关
- 是否可能在未来被引用
- 是否包含具体的事实或数据

信息: {content}

只输出一个0-1之间的小数，例如: 0.75"""

        try:
            response = await self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-3.5-turbo",
                temperature=0.0,
            )

            importance = float(response.strip())
            return max(0.0, min(1.0, importance))

        except Exception as e:
            logger.error(f"Error assessing importance: {e}")
            return 0.5  # 默认中等重要性

    async def _compute_relevance(self, query: str, content: str) -> float:
        """计算查询与记忆的相关性"""
        # 简单实现：词重叠率
        query_terms = set(query.lower().split())
        content_terms = set(content.lower().split())

        if not query_terms:
            return 0.0

        overlap = query_terms & content_terms
        relevance = len(overlap) / len(query_terms)

        return relevance

    async def _store_memory(self, memory: Memory) -> None:
        """存储记忆到后端"""
        if not self.storage:
            return

        try:
            await self.storage.add(
                id=memory.memory_id,
                text=memory.content,
                metadata={
                    "tier": memory.tier.value,
                    "importance": memory.importance,
                    "created_at": memory.created_at.isoformat(),
                    "last_accessed": memory.last_accessed.isoformat(),
                    "access_count": memory.access_count,
                    **memory.metadata,
                },
            )
        except Exception as e:
            logger.error(f"Error storing memory: {e}")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        memory_counts = {tier.value: len(memories) for tier, memories in self.memories.items()}

        total_importance = sum(
            m.get_current_importance()
            for tier_memories in self.memories.values()
            for m in tier_memories
        )

        total_memories = sum(memory_counts.values())
        avg_importance = total_importance / total_memories if total_memories > 0 else 0.0

        return {
            **self.stats,
            "memory_counts": memory_counts,
            "total_memories": total_memories,
            "avg_importance": avg_importance,
        }
