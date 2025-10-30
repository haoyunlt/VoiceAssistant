"""
Conflict Resolution for Multi-Agent System
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts"""

    RESOURCE = "resource"  # Resource contention
    PRIORITY = "priority"  # Priority conflict
    INFORMATION = "information"  # Contradictory information
    GOAL = "goal"  # Conflicting goals


class ConflictResolutionStrategy(Enum):
    """Conflict resolution strategies"""

    VOTING = "voting"
    PRIORITY_BASED = "priority_based"
    CONSENSUS = "consensus"
    COORDINATOR_DECISION = "coordinator_decision"
    NEGOTIATION = "negotiation"


class Conflict:
    """Represents a conflict between agents"""

    def __init__(
        self,
        conflict_id: str,
        agents_involved: list[str],
        conflict_type: ConflictType,
        description: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.conflict_id = conflict_id
        self.agents_involved = agents_involved
        self.conflict_type = conflict_type
        self.description = description
        self.context = context or {}
        self.resolution: str | None = None
        self.resolved = False


class ConflictResolver:
    """Resolves conflicts between agents"""

    def __init__(
        self, default_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.VOTING
    ) -> None:
        self.default_strategy = default_strategy
        self.conflict_history: list[Conflict] = []
        self.agent_priorities: dict[str, int] = {}

    def set_agent_priority(self, agent_id: str, priority: int) -> None:
        """Set agent priority for priority-based resolution"""
        self.agent_priorities[agent_id] = priority

    async def resolve(
        self, conflict: Conflict, strategy: ConflictResolutionStrategy | None = None
    ) -> str | None:  # type: ignore [return-value]
        """Resolve conflict using specified strategy"""
        strategy = strategy or self.default_strategy
        logger.info(f"Resolving conflict {conflict.conflict_id} using {strategy.value} strategy")

        try:
            if strategy == ConflictResolutionStrategy.VOTING:
                resolution = await self._voting_resolution(conflict)
            elif strategy == ConflictResolutionStrategy.PRIORITY_BASED:
                resolution = await self._priority_based_resolution(conflict)
            elif strategy == ConflictResolutionStrategy.CONSENSUS:
                resolution = await self._consensus_resolution(conflict)
            elif strategy == ConflictResolutionStrategy.COORDINATOR_DECISION:
                resolution = await self._coordinator_decision(conflict)
            elif strategy == ConflictResolutionStrategy.NEGOTIATION:
                resolution = await self._negotiation_resolution(conflict)
            else:
                resolution = "No resolution strategy available"

            conflict.resolution = resolution
            conflict.resolved = True
            self.conflict_history.append(conflict)

            logger.info(f"Conflict {conflict.conflict_id} resolved: {resolution}")
            return resolution

        except Exception as e:
            logger.error(f"Failed to resolve conflict: {e}")
            return f"Resolution failed: {str(e)}"

    async def _voting_resolution(self, conflict: Conflict) -> str | None:  # type: ignore [return-value]
        """Resolve by voting"""
        # In a real implementation, we would collect votes from agents
        # For now, use majority rule simulation
        votes = conflict.context.get("votes", {})

        if not votes:
            return "Insufficient votes for resolution"

        # Count votes
        vote_counts: dict[str, int] = {}
        for _agent_id, vote in votes.items():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        # Find majority
        max_votes = max(vote_counts.values())
        winners = [option for option, count in vote_counts.items() if count == max_votes]

        if len(winners) == 1:
            return f"Voted resolution: {winners[0]}"
        else:
            return f"Tie between: {', '.join(winners)}. Coordinator decision needed."

    async def _priority_based_resolution(self, conflict: Conflict) -> str | None:  # type: ignore [return-value]
        """Resolve based on agent priorities"""
        # Find highest priority agent
        highest_priority = -1
        priority_agent = None

        for agent_id in conflict.agents_involved:
            priority = self.agent_priorities.get(agent_id, 0)
            if priority > highest_priority:
                highest_priority = priority
                priority_agent = agent_id

        if priority_agent:
            agent_position = conflict.context.get("positions", {}).get(priority_agent)
            return f"Resolved in favor of {priority_agent} (priority: {highest_priority}): {agent_position}"
        else:
            return "No priority agent found"

    async def _consensus_resolution(self, conflict: Conflict) -> str | None:  # type: ignore [return-value]
        """Resolve by finding consensus"""
        positions = conflict.context.get("positions", {})

        if len(positions) < 2:
            return "Insufficient positions for consensus"

        # Find common ground
        # In a real implementation, use NLP to find similarity
        # For now, simple comparison
        position_values = list(positions.values())

        if len(set(position_values)) == 1:
            return f"Consensus reached: {position_values[0]}"
        else:
            # Try to find middle ground
            return f"Consensus building: Combine elements from all positions: {', '.join(set(position_values))}"

    async def _coordinator_decision(self, conflict: Conflict) -> str | None:  # type: ignore [return-value]
        """Coordinator makes final decision"""
        # In a real implementation, coordinator agent would analyze and decide
        # For now, return structured decision
        return f"Coordinator decision: Resolved {conflict.conflict_type.value} conflict - {conflict.description}"

    async def _negotiation_resolution(self, conflict: Conflict) -> str | None:  # type: ignore [return-value]
        """Resolve through negotiation"""
        # Implement multi-round negotiation
        max_rounds = conflict.context.get("max_negotiation_rounds", 3)

        # Simulate negotiation rounds
        for _round_num in range(max_rounds):
            # In real implementation, agents would exchange proposals
            # and counter-proposals
            pass

        return f"Negotiated resolution after {max_rounds} rounds"

    def get_conflict_statistics(self) -> dict[str, Any]:  # type: ignore [return-value]
        """Get conflict resolution statistics"""
        conflict_types: dict[str, int] = {}
        total_conflicts = len(self.conflict_history)
        resolved_conflicts = sum(1 for c in self.conflict_history if c.resolved)

        for conflict in self.conflict_history:
            conflict_type = conflict.conflict_type.value
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1

        return {
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "resolution_rate": resolved_conflicts / total_conflicts if total_conflicts > 0 else 0,
            "conflict_types": conflict_types,
        }


class ConflictDetector:
    """Detect potential conflicts between agents"""

    def __init__(self) -> None:
        self.watched_resources: dict[str, list[str]] = {}

    def detect_resource_conflict(self, resource_id: str, requesting_agent: str) -> Conflict | None:  # type: ignore [return-value]
        """Detect resource contention"""
        if resource_id in self.watched_resources:
            current_users = self.watched_resources[resource_id]
            if current_users:
                return Conflict(
                    conflict_id=f"resource_{resource_id}_{requesting_agent}",
                    agents_involved=current_users + [requesting_agent],
                    conflict_type=ConflictType.RESOURCE,
                    description=f"Multiple agents requesting resource: {resource_id}",
                    context={"resource_id": resource_id},
                )

        return None

    def detect_information_conflict(self, information: dict[str, Any]) -> Conflict | None:
        """Detect contradictory information from agents"""
        # Check for contradictions
        agents = list(information.keys())
        values = list(information.values())

        # If same key has different values from different agents
        if len(set(map(str, values))) > 1:
            return Conflict(
                conflict_id=f"info_conflict_{hash(str(information))}",
                agents_involved=agents,
                conflict_type=ConflictType.INFORMATION,
                description="Agents provided contradictory information",
                context={"information": information},
            )

        return None

    def register_resource(self, resource_id: str, agent_id: str) -> None:
        """Register agent's use of resource"""
        if resource_id not in self.watched_resources:
            self.watched_resources[resource_id] = []
        if agent_id not in self.watched_resources[resource_id]:
            self.watched_resources[resource_id].append(agent_id)

    def release_resource(self, resource_id: str, agent_id: str) -> None:
        """Release agent's use of resource"""
        if resource_id in self.watched_resources:
            if agent_id in self.watched_resources[resource_id]:
                self.watched_resources[resource_id].remove(agent_id)
