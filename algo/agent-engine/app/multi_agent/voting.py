"""
投票与共识协作模块

多个 Agent 通过投票机制达成共识决策。
"""

import logging
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class VotingMethod(Enum):
    """投票方法"""

    MAJORITY = "majority"  # 简单多数
    WEIGHTED = "weighted"  # 加权投票
    RANKED_CHOICE = "ranked_choice"  # 排序选择投票
    CONSENSUS = "consensus"  # 共识决（需全体同意）
    SUPERMAJORITY = "supermajority"  # 绝对多数（2/3）


@dataclass
class Vote:
    """投票"""

    agent_id: str
    choice: str
    confidence: float  # 0-1
    reasoning: str
    weight: float = 1.0  # 投票权重


@dataclass
class VotingResult:
    """投票结果"""

    question: str
    winner: str
    votes: list[Vote]
    vote_distribution: dict[str, int]
    confidence: float  # 整体置信度
    reasoning: str
    is_consensus: bool  # 是否达成共识


class VotingCoordinator:
    """
    投票协调器

    组织多个 Agent 进行投票决策。

    用法:
        coordinator = VotingCoordinator()

        # 准备 Agents
        agents = [agent1, agent2, agent3]

        # 投票
        result = await coordinator.vote(
            question="Should we adopt GraphQL?",
            options=["Yes", "No", "Need more research"],
            agents=agents,
            method=VotingMethod.WEIGHTED
        )
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "gpt-4",
        confidence_threshold: float = 0.6,
        supermajority_ratio: float = 2.0 / 3.0,
    ):
        """
        初始化投票协调器

        Args:
            llm_client: LLM 客户端
            model: 使用的模型
            confidence_threshold: 置信度阈值
            supermajority_ratio: 绝对多数比例
        """
        self.llm_client = llm_client
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.supermajority_ratio = supermajority_ratio

        logger.info(
            f"VotingCoordinator initialized (confidence_threshold={confidence_threshold})"
        )

    async def vote(
        self,
        question: str,
        options: list[str],
        agents: list[dict],
        method: VotingMethod = VotingMethod.MAJORITY,
        context: dict | None = None,
    ) -> VotingResult:
        """
        执行投票

        Args:
            question: 投票问题
            options: 选项列表
            agents: Agent 列表
            method: 投票方法
            context: 上下文信息

        Returns:
            投票结果
        """
        logger.info(f"Starting vote: {question}")
        logger.info(f"Options: {options}, Agents: {len(agents)}, Method: {method.value}")

        # 收集投票
        votes = []
        for agent in agents:
            vote = await self._get_agent_vote(question, options, agent, context)
            votes.append(vote)
            logger.debug(
                f"Agent {agent['id']} voted: {vote.choice} (confidence: {vote.confidence:.2f})"
            )

        # 计算结果
        if method == VotingMethod.MAJORITY:
            result = self._majority_vote(question, votes)
        elif method == VotingMethod.WEIGHTED:
            result = self._weighted_vote(question, votes)
        elif method == VotingMethod.RANKED_CHOICE:
            result = self._ranked_choice_vote(question, votes)
        elif method == VotingMethod.CONSENSUS:
            result = self._consensus_vote(question, votes)
        elif method == VotingMethod.SUPERMAJORITY:
            result = self._supermajority_vote(question, votes)
        else:
            result = self._majority_vote(question, votes)

        logger.info(f"Vote result: {result.winner} (consensus: {result.is_consensus})")

        return result

    async def _get_agent_vote(
        self,
        question: str,
        options: list[str],
        agent: dict,
        context: dict | None,
    ) -> Vote:
        """获取 Agent 的投票"""
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])

        context_text = ""
        if context:
            context_text = f"\n背景信息:\n{context.get('description', '')}"

        prompt = f"""你是一个决策助手。请针对以下问题进行投票。

问题: {question}

选项:
{options_text}
{context_text}

请以 JSON 格式输出你的投票:
{{
  "choice": "选项文本",
  "confidence": 0.0-1.0,
  "reasoning": "投票理由（2-3句话）"
}}

要求:
1. 仔细分析各选项的优缺点
2. 给出你的置信度（0-1）
3. 简要说明你的理由"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = response  # 假设返回 JSON

        return Vote(
            agent_id=agent["id"],
            choice=result.get("choice", options[0]),
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning", ""),
            weight=agent.get("weight", 1.0),
        )

    def _majority_vote(self, question: str, votes: list[Vote]) -> VotingResult:
        """简单多数投票"""
        vote_counts = Counter(vote.choice for vote in votes)
        winner = vote_counts.most_common(1)[0][0]
        winner_count = vote_counts[winner]

        # 检查是否真的是多数（>50%）
        is_consensus = winner_count > len(votes) / 2

        # 计算整体置信度
        winner_votes = [v for v in votes if v.choice == winner]
        avg_confidence = (
            sum(v.confidence for v in winner_votes) / len(winner_votes)
            if winner_votes
            else 0.0
        )

        # 合并理由
        reasoning = self._merge_reasoning(winner_votes)

        return VotingResult(
            question=question,
            winner=winner,
            votes=votes,
            vote_distribution=dict(vote_counts),
            confidence=avg_confidence,
            reasoning=reasoning,
            is_consensus=is_consensus,
        )

    def _weighted_vote(self, question: str, votes: list[Vote]) -> VotingResult:
        """加权投票"""
        weighted_counts = {}
        for vote in votes:
            weighted_counts[vote.choice] = (
                weighted_counts.get(vote.choice, 0.0) + vote.weight
            )

        winner = max(weighted_counts.keys(), key=lambda k: weighted_counts[k])

        # 计算置信度（加权平均）
        winner_votes = [v for v in votes if v.choice == winner]
        total_weight = sum(v.weight for v in winner_votes)
        weighted_confidence = (
            sum(v.confidence * v.weight for v in winner_votes) / total_weight
            if total_weight > 0
            else 0.0
        )

        # 检查是否达成共识（加权多数 >50%）
        total_votes_weight = sum(v.weight for v in votes)
        is_consensus = weighted_counts[winner] > total_votes_weight / 2

        reasoning = self._merge_reasoning(winner_votes)

        return VotingResult(
            question=question,
            winner=winner,
            votes=votes,
            vote_distribution={k: int(v) for k, v in weighted_counts.items()},
            confidence=weighted_confidence,
            reasoning=reasoning,
            is_consensus=is_consensus,
        )

    def _ranked_choice_vote(self, question: str, votes: list[Vote]) -> VotingResult:
        """排序选择投票（简化实现）"""
        # 简化版：使用加权置信度作为排名
        weighted_scores = {}
        for vote in votes:
            score = vote.confidence * vote.weight
            weighted_scores[vote.choice] = weighted_scores.get(vote.choice, 0.0) + score

        winner = max(weighted_scores.keys(), key=lambda k: weighted_scores[k])

        winner_votes = [v for v in votes if v.choice == winner]
        avg_confidence = (
            sum(v.confidence for v in winner_votes) / len(winner_votes)
            if winner_votes
            else 0.0
        )

        reasoning = self._merge_reasoning(winner_votes)

        return VotingResult(
            question=question,
            winner=winner,
            votes=votes,
            vote_distribution={k: int(v) for k, v in weighted_scores.items()},
            confidence=avg_confidence,
            reasoning=reasoning,
            is_consensus=avg_confidence >= self.confidence_threshold,
        )

    def _consensus_vote(self, question: str, votes: list[Vote]) -> VotingResult:
        """共识决（需全体同意）"""
        choices = {vote.choice for vote in votes}

        if len(choices) == 1:
            # 全体一致
            winner = list(choices)[0]
            avg_confidence = sum(v.confidence for v in votes) / len(votes)
            is_consensus = True
            reasoning = "全体一致同意：" + self._merge_reasoning(votes)
        else:
            # 未达成共识
            vote_counts = Counter(vote.choice for vote in votes)
            winner = vote_counts.most_common(1)[0][0]
            winner_votes = [v for v in votes if v.choice == winner]
            avg_confidence = (
                sum(v.confidence for v in winner_votes) / len(winner_votes)
                if winner_votes
                else 0.0
            )
            is_consensus = False
            reasoning = f"未达成共识，多数选择为：{winner}"

        return VotingResult(
            question=question,
            winner=winner,
            votes=votes,
            vote_distribution=dict(Counter(vote.choice for vote in votes)),
            confidence=avg_confidence,
            reasoning=reasoning,
            is_consensus=is_consensus,
        )

    def _supermajority_vote(self, question: str, votes: list[Vote]) -> VotingResult:
        """绝对多数投票（2/3）"""
        vote_counts = Counter(vote.choice for vote in votes)
        winner = vote_counts.most_common(1)[0][0]
        winner_count = vote_counts[winner]

        # 检查是否达到绝对多数
        is_consensus = winner_count >= len(votes) * self.supermajority_ratio

        winner_votes = [v for v in votes if v.choice == winner]
        avg_confidence = (
            sum(v.confidence for v in winner_votes) / len(winner_votes)
            if winner_votes
            else 0.0
        )

        if is_consensus:
            reasoning = f"达到绝对多数（{winner_count}/{len(votes)}）：" + self._merge_reasoning(
                winner_votes
            )
        else:
            reasoning = f"未达到绝对多数（需{int(len(votes) * self.supermajority_ratio)}票）"

        return VotingResult(
            question=question,
            winner=winner,
            votes=votes,
            vote_distribution=dict(vote_counts),
            confidence=avg_confidence,
            reasoning=reasoning,
            is_consensus=is_consensus,
        )

    def _merge_reasoning(self, votes: list[Vote]) -> str:
        """合并多个投票理由"""
        if not votes:
            return ""

        # 选择前3个最高置信度的理由
        sorted_votes = sorted(votes, key=lambda v: v.confidence, reverse=True)
        top_reasons = [v.reasoning for v in sorted_votes[:3]]

        return "; ".join(top_reasons)

    async def multi_round_vote(
        self,
        question: str,
        options: list[str],
        agents: list[dict],
        max_rounds: int = 3,
    ) -> VotingResult:
        """
        多轮投票（直到达成共识或达到最大轮数）

        Args:
            question: 投票问题
            options: 选项列表
            agents: Agent 列表
            max_rounds: 最大轮数

        Returns:
            最终投票结果
        """
        logger.info(f"Starting multi-round vote (max_rounds={max_rounds})")

        for round_num in range(1, max_rounds + 1):
            logger.info(f"Round {round_num}/{max_rounds}")

            result = await self.vote(
                question=question,
                options=options,
                agents=agents,
                method=VotingMethod.WEIGHTED,
            )

            if result.is_consensus:
                logger.info(f"Consensus reached in round {round_num}")
                return result

            # 未达成共识，允许 Agents 查看当前投票分布并重新考虑
            # （在实际实现中，可以将投票分布作为上下文传递给下一轮）

        logger.warning("Max rounds reached without consensus")
        return result

