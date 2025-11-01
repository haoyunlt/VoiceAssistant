"""
Multi-Agent Collaboration Framework
"""

from app.core.multi_agent.communication import MessageBus, MessageRouter
from app.core.multi_agent.conflict_resolver import ConflictResolver
from app.core.multi_agent.coordinator import Agent, AgentRole, Message, MultiAgentCoordinator

__all__ = [
    "MultiAgentCoordinator",
    "Agent",
    "AgentRole",
    "Message",
    "MessageBus",
    "MessageRouter",
    "ConflictResolver",
]
