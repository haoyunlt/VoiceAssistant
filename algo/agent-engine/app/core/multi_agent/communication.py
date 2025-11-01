"""
Multi-Agent Communication Module
"""

import asyncio
import logging
from collections.abc import Callable

from app.core.multi_agent.coordinator import Message

logger = logging.getLogger(__name__)


class MessageBus:
    """Central message bus for agent communication"""

    def __init__(self, _max_queue_size: int = 1000):
        self.queue: asyncio.Queue[Message] | None = None
        self.subscribers: dict[str, list[Callable]] = {}
        self.message_history: list[Message] = []
        self.is_running = False

    async def start(self) -> None:
        """Start message bus"""
        self.is_running = True
        asyncio.create_task(self._process_messages())
        logger.info("Message bus started")

    async def stop(self) -> None:
        """Stop message bus"""
        self.is_running = False
        logger.info("Message bus stopped")

    async def publish(self, message: Message) -> None:
        """Publish message to bus"""
        try:
            await self.queue.put(message)  # type: ignore [union-attr]
            self.message_history.append(message)
            logger.debug(f"Published message from {message.sender} to {message.receiver}")
        except asyncio.QueueFull:
            logger.warning("Message queue full, message dropped")

    def subscribe(self, agent_id: str, callback: Callable) -> None:
        """Subscribe agent to messages"""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        self.subscribers[agent_id].append(callback)
        logger.info(f"Agent {agent_id} subscribed to message bus")

    def unsubscribe(self, agent_id: str) -> None:
        """Unsubscribe agent from messages"""
        if agent_id in self.subscribers:
            del self.subscribers[agent_id]
            logger.info(f"Agent {agent_id} unsubscribed from message bus")

    async def _process_messages(self) -> None:
        """Process messages from queue"""
        while self.is_running:
            try:
                message = await asyncio.wait_for(self.queue.get(), timeout=1.0)  # type: ignore [union-attr]
                await self._route_message(message)
            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message processing error: {e}")

    async def _route_message(self, message: Message) -> None:
        """Route message to subscribers"""
        receiver = message.receiver

        # Broadcast message
        if receiver == "broadcast":
            for agent_id, callbacks in self.subscribers.items():
                for callback in callbacks:
                    try:
                        await callback(message)
                    except Exception as e:
                        logger.error(f"Callback error for {agent_id}: {e}")
        # Direct message
        elif receiver in self.subscribers:
            for callback in self.subscribers[receiver]:
                try:
                    await callback(message)
                except Exception as e:
                    logger.error(f"Callback error for {receiver}: {e}")
        else:
            logger.warning(f"No subscriber found for {receiver}")

    def get_message_history(self, agent_id: str | None = None, limit: int = 100) -> list[Message]:  # type: ignore [return-value]
        """Get message history"""
        if agent_id:
            history = [
                msg
                for msg in self.message_history
                if msg.sender == agent_id or msg.receiver == agent_id
            ]
        else:
            history = self.message_history

        return history[-limit:]


class MessageRouter:
    """Route messages between agents with different strategies"""

    def __init__(self) -> None:
        self.routing_table: dict[str, str] = {}
        self.routing_strategy = "direct"

    def set_route(self, from_agent: str, to_agent: str) -> None:
        """Set routing rule"""
        self.routing_table[from_agent] = to_agent

    def route(self, message: Message) -> str:
        """Determine message destination"""
        if self.routing_strategy == "direct":
            return message.receiver
        elif self.routing_strategy == "rule_based":
            return self.routing_table.get(message.sender, message.receiver)
        elif self.routing_strategy == "round_robin":
            # Implement round-robin routing
            return message.receiver
        else:
            return message.receiver

    def set_strategy(self, strategy: str) -> None:
        """Set routing strategy"""
        if strategy in ["direct", "rule_based", "round_robin", "priority"]:
            self.routing_strategy = strategy
        else:
            logger.warning(f"Unknown routing strategy: {strategy}")


class MessageQueue:
    """Priority message queue for agents"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.messages: list[Message] = []
        self.lock = asyncio.Lock()

    async def enqueue(self, message: Message) -> None:
        """Add message to queue with priority"""
        async with self.lock:
            if len(self.messages) >= self.max_size:
                # Remove lowest priority message
                self.messages.sort(key=lambda m: m.priority)
                self.messages.pop(0)

            self.messages.append(message)
            # Sort by priority (higher first) and timestamp
            self.messages.sort(key=lambda m: (-m.priority, m.timestamp))

    async def dequeue(self) -> Message | None:  # type: ignore [return-value]
        """Get highest priority message"""
        async with self.lock:
            if self.messages:
                return self.messages.pop(0)
            return None

    async def peek(self) -> Message | None:  # type: ignore [return-value]
        """Peek at next message without removing"""
        async with self.lock:
            if self.messages:
                return self.messages[0]
            return None

    def size(self) -> int:  # type: ignore [return-value]
        """Get queue size"""
        return len(self.messages)

    def is_empty(self) -> bool:  # type: ignore [return-value]
        """Check if queue is empty"""
        return len(self.messages) == 0
