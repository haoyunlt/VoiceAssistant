"""
Agent 间通信模块

包含消息总线、共享黑板、Agent 注册等功能。
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """消息优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class AgentMessage:
    """Agent 消息"""

    sender_id: str
    receiver_id: str | None  # None 表示广播
    topic: str
    content: Any
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageBus:
    """
    消息总线

    基于 Redis Pub/Sub 或内存实现的消息总线。

    用法:
        bus = MessageBus(redis_client)

        # 订阅主题
        await bus.subscribe("task_updates", handler_function)

        # 发布消息
        await bus.publish("task_updates", AgentMessage(...))

        # 广播消息
        await bus.broadcast("system_alert", AgentMessage(...))
    """

    def __init__(self, redis_client: Any | None = None):
        """
        初始化消息总线

        Args:
            redis_client: Redis 客户端（可选，否则使用内存）
        """
        self.redis = redis_client
        self.use_redis = redis_client is not None

        # 内存订阅者（当没有 Redis 时）
        self.subscribers: dict[str, list[Callable]] = {}

        # 消息历史（用于调试）
        self.message_history: list[AgentMessage] = []
        self.max_history_size = 1000

        logger.info(f"MessageBus initialized (backend={'redis' if self.use_redis else 'memory'})")

    async def subscribe(self, topic: str, handler: Callable) -> None:
        """
        订阅主题

        Args:
            topic: 主题名称
            handler: 消息处理函数 async def handler(message: AgentMessage)
        """
        if self.use_redis:
            # Redis Pub/Sub 实现
            # 实际项目中需要启动独立的订阅任务
            logger.info(f"Subscribed to Redis topic: {topic}")
            # await self._redis_subscribe(topic, handler)
        else:
            # 内存实现
            if topic not in self.subscribers:
                self.subscribers[topic] = []
            self.subscribers[topic].append(handler)
            logger.info(f"Subscribed to topic: {topic}")

    async def publish(self, topic: str, message: AgentMessage):
        """
        发布消息到主题

        Args:
            topic: 主题名称
            message: 消息对象
        """
        # 记录历史
        self._add_to_history(message)

        if self.use_redis:
            # Redis Pub/Sub
            await self.redis.publish(topic, json.dumps(self._message_to_dict(message)))
            logger.debug(
                f"Published to Redis topic {topic}: {message.sender_id} -> {message.receiver_id}"
            )
        else:
            # 内存实现
            if topic in self.subscribers:
                for handler in self.subscribers[topic]:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")

            logger.debug(
                f"Published to topic {topic}: {message.sender_id} -> {message.receiver_id}"
            )

    async def broadcast(self, topic: str, content: Any, sender_id: str):
        """
        广播消息

        Args:
            topic: 主题名称
            content: 消息内容
            sender_id: 发送者 ID
        """
        message = AgentMessage(
            sender_id=sender_id,
            receiver_id=None,  # 广播
            topic=topic,
            content=content,
            priority=MessagePriority.NORMAL,
        )

        await self.publish(topic, message)

    async def send_direct(self, receiver_id: str, content: Any, sender_id: str):
        """
        点对点发送消息

        Args:
            receiver_id: 接收者 ID
            content: 消息内容
            sender_id: 发送者 ID
        """
        topic = f"agent.{receiver_id}"  # 私有主题

        message = AgentMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            topic=topic,
            content=content,
            priority=MessagePriority.NORMAL,
        )

        await self.publish(topic, message)

    def get_message_history(
        self, topic: str | None = None, limit: int = 100
    ) -> list[AgentMessage]:
        """
        获取消息历史

        Args:
            topic: 主题过滤（可选）
            limit: 返回数量限制

        Returns:
            消息列表
        """
        if topic:
            filtered = [msg for msg in self.message_history if msg.topic == topic]
        else:
            filtered = self.message_history

        return filtered[-limit:]

    def _add_to_history(self, message: AgentMessage):
        """添加到历史"""
        self.message_history.append(message)
        if len(self.message_history) > self.max_history_size:
            self.message_history.pop(0)

    def _message_to_dict(self, message: AgentMessage) -> dict:
        """消息转字典"""
        return {
            "sender_id": message.sender_id,
            "receiver_id": message.receiver_id,
            "topic": message.topic,
            "content": message.content,
            "priority": message.priority.value,
            "timestamp": message.timestamp,
            "metadata": message.metadata,
        }


class Blackboard:
    """
    共享黑板

    Agent 之间共享状态的存储。

    用法:
        blackboard = Blackboard(redis_client)

        # 写入数据
        await blackboard.write("current_task", {"status": "in_progress"})

        # 读取数据
        task = await blackboard.read("current_task")

        # 监听变化
        await blackboard.watch("current_task", callback)
    """

    def __init__(self, redis_client: Any | None = None):
        """
        初始化共享黑板

        Args:
            redis_client: Redis 客户端（可选，否则使用内存）
        """
        self.redis = redis_client
        self.use_redis = redis_client is not None

        # 内存存储
        self.storage: dict[str, Any] = {}

        # 监听器
        self.watchers: dict[str, list[Callable]] = {}

        logger.info(f"Blackboard initialized (backend={'redis' if self.use_redis else 'memory'})")

    async def write(self, key: str, value: Any, ttl: int | None = None):
        """
        写入数据

        Args:
            key: 键
            value: 值
            ttl: 过期时间（秒），可选
        """
        if self.use_redis:
            # Redis 实现
            serialized = json.dumps(value)
            if ttl:
                await self.redis.setex(f"blackboard:{key}", ttl, serialized)
            else:
                await self.redis.set(f"blackboard:{key}", serialized)
        else:
            # 内存实现
            self.storage[key] = value

        logger.debug(f"Blackboard write: {key}")

        # 通知监听器
        await self._notify_watchers(key, value)

    async def read(self, key: str) -> Any | None:
        """
        读取数据

        Args:
            key: 键

        Returns:
            值，如果不存在返回 None
        """
        if self.use_redis:
            # Redis 实现
            value = await self.redis.get(f"blackboard:{key}")
            return json.loads(value) if value else None
        else:
            # 内存实现
            return self.storage.get(key)

    async def update(self, key: str, updates: dict[str, Any]):
        """
        更新数据（字典合并）

        Args:
            key: 键
            updates: 更新的字段
        """
        current = await self.read(key) or {}
        if isinstance(current, dict):
            current.update(updates)
            await self.write(key, current)
        else:
            logger.warning(f"Cannot update non-dict value for key: {key}")

    async def delete(self, key: str):
        """删除数据"""
        if self.use_redis:
            await self.redis.delete(f"blackboard:{key}")
        else:
            self.storage.pop(key, None)

        logger.debug(f"Blackboard delete: {key}")

    async def watch(self, key: str, callback: Callable):
        """
        监听键的变化

        Args:
            key: 键
            callback: 回调函数 async def callback(key, new_value)
        """
        if key not in self.watchers:
            self.watchers[key] = []
        self.watchers[key].append(callback)

        logger.debug(f"Watching key: {key}")

    async def _notify_watchers(self, key: str, value: Any):
        """通知监听器"""
        if key in self.watchers:
            for callback in self.watchers[key]:
                try:
                    await callback(key, value)
                except Exception as e:
                    logger.error(f"Error in watcher callback: {e}")

    async def list_keys(self, pattern: str = "*") -> list[str]:
        """
        列出所有键

        Args:
            pattern: 匹配模式（仅 Redis 支持通配符）

        Returns:
            键列表
        """
        if self.use_redis:
            keys = await self.redis.keys(f"blackboard:{pattern}")
            return [k.decode().replace("blackboard:", "") for k in keys]
        else:
            # 内存实现：简单匹配
            if pattern == "*":
                return list(self.storage.keys())
            else:
                # 简单的前缀匹配
                prefix = pattern.replace("*", "")
                return [k for k in self.storage if k.startswith(prefix)]


class AgentRegistry:
    """
    Agent 注册中心

    管理 Agent 的注册、发现、状态。

    用法:
        registry = AgentRegistry(redis_client)

        # 注册 Agent
        await registry.register(
            agent_id="agent_001",
            capabilities=["search", "summarize"],
            metadata={"role": "researcher"}
        )

        # 发现 Agent
        agents = await registry.discover(capabilities=["search"])

        # 心跳
        await registry.heartbeat("agent_001")
    """

    def __init__(self, redis_client: Any | None = None):
        """
        初始化 Agent 注册中心

        Args:
            redis_client: Redis 客户端（可选）
        """
        self.redis = redis_client
        self.use_redis = redis_client is not None

        # 内存存储
        self.agents: dict[str, dict] = {}

        # 心跳超时（秒）
        self.heartbeat_timeout = 60

        logger.info("AgentRegistry initialized")

    async def register(
        self,
        agent_id: str,
        capabilities: list[str],
        metadata: dict | None = None,
    ):
        """
        注册 Agent

        Args:
            agent_id: Agent ID
            capabilities: 能力列表
            metadata: 元数据
        """
        agent_info = {
            "agent_id": agent_id,
            "capabilities": capabilities,
            "metadata": metadata or {},
            "status": "online",
            "last_heartbeat": datetime.now().timestamp(),
        }

        if self.use_redis:
            # Redis 实现
            await self.redis.hset(
                "agent_registry",
                agent_id,
                json.dumps(agent_info),
            )
            # 设置心跳过期
            await self.redis.setex(
                f"agent_heartbeat:{agent_id}",
                self.heartbeat_timeout,
                "1",
            )
        else:
            # 内存实现
            self.agents[agent_id] = agent_info

        logger.info(f"Agent registered: {agent_id} with capabilities {capabilities}")

    async def unregister(self, agent_id: str):
        """注销 Agent"""
        if self.use_redis:
            await self.redis.hdel("agent_registry", agent_id)
            await self.redis.delete(f"agent_heartbeat:{agent_id}")
        else:
            self.agents.pop(agent_id, None)

        logger.info(f"Agent unregistered: {agent_id}")

    async def discover(self, capabilities: list[str] | None = None) -> list[dict]:
        """
        发现 Agent

        Args:
            capabilities: 需要的能力列表（可选）

        Returns:
            匹配的 Agent 列表
        """
        if self.use_redis:
            # Redis 实现
            all_agents_data = await self.redis.hgetall("agent_registry")
            all_agents = [json.loads(v.decode()) for v in all_agents_data.values()]
        else:
            # 内存实现
            all_agents = list(self.agents.values())

        # 过滤能力
        if capabilities:
            filtered = []
            for agent in all_agents:
                agent_caps = set(agent.get("capabilities", []))
                required_caps = set(capabilities)
                if required_caps.issubset(agent_caps):
                    filtered.append(agent)
            return filtered
        else:
            return all_agents

    async def heartbeat(self, agent_id: str):
        """
        Agent 心跳

        Args:
            agent_id: Agent ID
        """
        if self.use_redis:
            # 更新心跳时间
            await self.redis.setex(
                f"agent_heartbeat:{agent_id}",
                self.heartbeat_timeout,
                "1",
            )
        else:
            # 内存实现
            if agent_id in self.agents:
                self.agents[agent_id]["last_heartbeat"] = datetime.now().timestamp()

        logger.debug(f"Heartbeat from agent: {agent_id}")

    async def get_agent_status(self, agent_id: str) -> str | None:
        """获取 Agent 状态"""
        if self.use_redis:
            # 检查心跳是否存在
            exists = await self.redis.exists(f"agent_heartbeat:{agent_id}")
            return "online" if exists else "offline"
        else:
            agent = self.agents.get(agent_id)
            if agent:
                last_hb = agent.get("last_heartbeat", 0)
                if datetime.now().timestamp() - last_hb < self.heartbeat_timeout:
                    return "online"
            return "offline"

    async def list_all_agents(self) -> list[dict]:
        """列出所有 Agent"""
        return await self.discover()
