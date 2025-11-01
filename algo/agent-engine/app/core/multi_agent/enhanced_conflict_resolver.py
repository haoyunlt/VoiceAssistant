"""
Enhanced Conflict Resolver - 增强冲突解决器

实现多种冲突解决策略：
- 基于优先级的资源分配
- 投票仲裁机制
- 目标协商
- 协调者仲裁
"""

import logging
from enum import Enum
from typing import Any

from app.core.multi_agent.coordinator import Agent, AgentRole

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """冲突类型"""
    RESOURCE_CONTENTION = "resource_contention"  # 资源竞争
    OPINION_DISAGREEMENT = "opinion_disagreement"  # 意见分歧
    GOAL_CONFLICT = "goal_conflict"  # 目标冲突
    PRIORITY_CONFLICT = "priority_conflict"  # 优先级冲突
    DATA_INCONSISTENCY = "data_inconsistency"  # 数据不一致


class ResolutionStrategy(Enum):
    """解决策略"""
    PRIORITY_BASED = "priority_based"
    VOTING = "voting"
    NEGOTIATION = "negotiation"
    COORDINATOR_ARBITRATION = "coordinator_arbitration"
    CONSENSUS = "consensus"


class Resolution:
    """冲突解决结果"""
    def __init__(
        self,
        conflict_type: ConflictType,
        strategy_used: ResolutionStrategy,
        winner: Agent | None,
        decision: str,
        metadata: dict | None = None
    ):
        self.conflict_type = conflict_type
        self.strategy_used = strategy_used
        self.winner = winner
        self.decision = decision
        self.metadata = metadata or {}


class EnhancedConflictResolver:
    """
    增强冲突解决器
    
    用法:
        resolver = EnhancedConflictResolver(llm_client, coordinator_agent)
        
        resolution = await resolver.resolve_conflict(
            agent1=researcher_agent,
            agent2=planner_agent,
            conflict_type=ConflictType.OPINION_DISAGREEMENT,
            context={"task": "市场调研"}
        )
    """
    
    def __init__(self, llm_client: Any, coordinator: Agent | None = None):
        self.llm_client = llm_client
        self.coordinator = coordinator
        
        # 统计信息
        self.stats = {
            "total_conflicts": 0,
            "resolved_conflicts": 0,
            "failed_resolutions": 0,
            "strategy_usage": {},
        }
        
        logger.info("EnhancedConflictResolver initialized")
    
    async def resolve_conflict(
        self,
        agent1: Agent,
        agent2: Agent,
        conflict_type: ConflictType,
        context: dict[str, Any]
    ) -> Resolution:
        """
        解决冲突
        
        Args:
            agent1: 冲突方1
            agent2: 冲突方2
            conflict_type: 冲突类型
            context: 上下文信息
            
        Returns:
            Resolution: 解决结果
        """
        self.stats["total_conflicts"] += 1
        
        logger.info(
            f"Resolving conflict: {conflict_type.value} between "
            f"{agent1.agent_id} and {agent2.agent_id}"
        )
        
        try:
            # 根据冲突类型选择策略
            if conflict_type == ConflictType.RESOURCE_CONTENTION:
                resolution = await self._resolve_by_priority(agent1, agent2, context)
            
            elif conflict_type == ConflictType.OPINION_DISAGREEMENT:
                resolution = await self._resolve_by_voting(agent1, agent2, context)
            
            elif conflict_type == ConflictType.GOAL_CONFLICT:
                resolution = await self._resolve_by_negotiation(agent1, agent2, context)
            
            elif conflict_type == ConflictType.PRIORITY_CONFLICT:
                resolution = await self._resolve_by_coordinator(agent1, agent2, context)
            
            else:
                # 默认：协调者仲裁
                resolution = await self._resolve_by_coordinator(agent1, agent2, context)
            
            # 更新统计
            self.stats["resolved_conflicts"] += 1
            self.stats["strategy_usage"][resolution.strategy_used.value] = \
                self.stats["strategy_usage"].get(resolution.strategy_used.value, 0) + 1
            
            logger.info(
                f"Conflict resolved using {resolution.strategy_used.value}, "
                f"winner: {resolution.winner.agent_id if resolution.winner else 'none'}"
            )
            
            return resolution
        
        except Exception as e:
            self.stats["failed_resolutions"] += 1
            logger.error(f"Failed to resolve conflict: {e}")
            raise
    
    async def _resolve_by_priority(
        self, agent1: Agent, agent2: Agent, context: dict
    ) -> Resolution:
        """基于优先级解决资源竞争"""
        # 1. 获取agent优先级
        priority1 = context.get("priority1", 5)  # 默认优先级5
        priority2 = context.get("priority2", 5)
        
        # 2. 比较优先级
        if priority1 > priority2:
            winner = agent1
            decision = f"Agent {agent1.agent_id} 获得资源（优先级: {priority1} > {priority2}）"
        elif priority2 > priority1:
            winner = agent2
            decision = f"Agent {agent2.agent_id} 获得资源（优先级: {priority2} > {priority1}）"
        else:
            # 优先级相同，根据角色权重决定
            winner = self._decide_by_role_weight(agent1, agent2)
            decision = f"Agent {winner.agent_id} 获得资源（角色权重优势）"
        
        return Resolution(
            conflict_type=ConflictType.RESOURCE_CONTENTION,
            strategy_used=ResolutionStrategy.PRIORITY_BASED,
            winner=winner,
            decision=decision,
            metadata={"priority1": priority1, "priority2": priority2}
        )
    
    async def _resolve_by_voting(
        self, agent1: Agent, agent2: Agent, context: dict
    ) -> Resolution:
        """通过投票解决意见分歧"""
        # 1. 收集意见
        opinion1 = context.get("opinion1", "")
        opinion2 = context.get("opinion2", "")
        
        # 2. 使用LLM作为评委进行评估
        prompt = f"""作为中立评委，评估两个Agent的意见，投票选出更合理的一方。

任务: {context.get('task', '')}

Agent {agent1.agent_id} 的意见:
{opinion1}

Agent {agent2.agent_id} 的意见:
{opinion2}

请分析两个意见的优劣，并投票选择更合理的一方。
只返回: "agent1" 或 "agent2"，以及简短理由（不超过50字）。

格式: agent1/agent2: 理由"""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "你是一个公正的评委。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
        )
        
        # 3. 解析投票结果
        if "agent1" in response.lower()[:10]:
            winner = agent1
        else:
            winner = agent2
        
        decision = response.strip()
        
        return Resolution(
            conflict_type=ConflictType.OPINION_DISAGREEMENT,
            strategy_used=ResolutionStrategy.VOTING,
            winner=winner,
            decision=decision,
            metadata={"opinion1": opinion1, "opinion2": opinion2}
        )
    
    async def _resolve_by_negotiation(
        self, agent1: Agent, agent2: Agent, context: dict
    ) -> Resolution:
        """通过协商解决目标冲突"""
        # 1. 获取双方目标
        goal1 = context.get("goal1", "")
        goal2 = context.get("goal2", "")
        
        # 2. 使用LLM生成折衷方案
        prompt = f"""两个Agent有不同的目标，请生成一个折衷方案。

Agent {agent1.agent_id} 的目标:
{goal1}

Agent {agent2.agent_id} 的目标:
{goal2}

请提出一个折衷方案，尽可能满足双方需求。
返回JSON格式:
{{
    "compromise": "折衷方案描述",
    "agent1_satisfaction": 0.7,  # 0-1，agent1的满意度
    "agent2_satisfaction": 0.8   # 0-1，agent2的满意度
}}"""

        response = await self.llm_client.chat(
            messages=[
                {"role": "system", "content": "你是一个擅长协商的调解者。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        # 3. 解析折衷方案
        import json
        try:
            result = json.loads(response.strip())
            decision = result["compromise"]
        except Exception as e:
            logger.warning(f"Failed to parse negotiation result: {e}")
            decision = "无法达成折衷方案"
        
        return Resolution(
            conflict_type=ConflictType.GOAL_CONFLICT,
            strategy_used=ResolutionStrategy.NEGOTIATION,
            winner=None,  # 协商没有赢家
            decision=decision,
            metadata={"goal1": goal1, "goal2": goal2}
        )
    
    async def _resolve_by_coordinator(
        self, agent1: Agent, agent2: Agent, context: dict
    ) -> Resolution:
        """协调者仲裁"""
        if not self.coordinator:
            # 降级：默认选择agent1
            return Resolution(
                conflict_type=ConflictType.PRIORITY_CONFLICT,
                strategy_used=ResolutionStrategy.COORDINATOR_ARBITRATION,
                winner=agent1,
                decision=f"默认选择 {agent1.agent_id}（无协调者）",
                metadata={}
            )
        
        # 1. 协调者分析冲突
        prompt = f"""作为协调者，仲裁以下冲突。

任务: {context.get('task', '')}

Agent {agent1.agent_id} ({agent1.role.value}):
{context.get('agent1_input', '')}

Agent {agent2.agent_id} ({agent2.role.value}):
{context.get('agent2_input', '')}

请做出仲裁决定，选择哪个Agent的方案更合理，或提出新方案。
返回JSON格式:
{{
    "winner": "agent1/agent2/none",
    "decision": "仲裁决定",
    "reasoning": "理由"
}}"""

        response = await self.coordinator.llm_client.chat(
            messages=[
                {"role": "system", "content": f"你是{self.coordinator.role.value}，负责协调。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        
        # 2. 解析仲裁结果
        import json
        try:
            result = json.loads(response.strip())
            winner_str = result.get("winner", "agent1")
            
            if winner_str == "agent1":
                winner = agent1
            elif winner_str == "agent2":
                winner = agent2
            else:
                winner = None
            
            decision = result.get("decision", "协调者仲裁")
        except Exception as e:
            logger.warning(f"Failed to parse arbitration result: {e}")
            winner = agent1
            decision = f"默认选择 {agent1.agent_id}"
        
        return Resolution(
            conflict_type=ConflictType.PRIORITY_CONFLICT,
            strategy_used=ResolutionStrategy.COORDINATOR_ARBITRATION,
            winner=winner,
            decision=decision,
            metadata={}
        )
    
    def _decide_by_role_weight(self, agent1: Agent, agent2: Agent) -> Agent:
        """根据角色权重决定优先级"""
        # 角色权重（数值越大，权重越高）
        role_weights = {
            AgentRole.COORDINATOR: 5,
            AgentRole.PLANNER: 4,
            AgentRole.RESEARCHER: 3,
            AgentRole.EXECUTOR: 2,
            AgentRole.REVIEWER: 1,
        }
        
        weight1 = role_weights.get(agent1.role, 0)
        weight2 = role_weights.get(agent2.role, 0)
        
        return agent1 if weight1 >= weight2 else agent2
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["resolved_conflicts"] / self.stats["total_conflicts"]
                if self.stats["total_conflicts"] > 0
                else 0.0
            )
        }

