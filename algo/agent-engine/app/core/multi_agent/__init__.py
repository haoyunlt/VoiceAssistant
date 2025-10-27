"""
Multi-Agent Collaboration Framework
"""

from .coordinator import MultiAgentCoordinator, Agent, AgentRole, Message
from .communication import MessageBus, MessageRouter
from .conflict_resolver import ConflictResolver

__all__ = [
    'MultiAgentCoordinator',
    'Agent',
    'AgentRole',
    'Message',
    'MessageBus',
    'MessageRouter',
    'ConflictResolver',
]

