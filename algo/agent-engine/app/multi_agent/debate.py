"""
辩论模式协作模块

多个 Agent 针对同一问题展开辩论，通过论证和反驳达成更好的结论。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DebateRole(Enum):
    """辩论角色"""

    PROPONENT = "proponent"  # 正方
    OPPONENT = "opponent"  # 反方
    JUDGE = "judge"  # 评审员
    MODERATOR = "moderator"  # 主持人


@dataclass
class DebateMessage:
    """辩论消息"""

    round_number: int
    agent_id: str
    role: DebateRole
    content: str
    argument_type: str  # "claim", "rebuttal", "evidence", "summary"
    timestamp: float


@dataclass
class DebateResult:
    """辩论结果"""

    topic: str
    winner: str | None  # Agent ID
    consensus: str  # 达成的共识
    final_score: dict[str, float]  # 各方得分
    transcript: list[DebateMessage]  # 辩论记录
    reasoning: str  # 评审理由


class DebateCoordinator:
    """
    辩论协调器

    组织多个 Agent 进行结构化辩论。

    用法:
        coordinator = DebateCoordinator(llm_client)

        # 创建正反方 Agent
        proponent = Agent(id="agent_pro", role="proponent", prompt=...)
        opponent = Agent(id="agent_con", role="opponent", prompt=...)
        judge = Agent(id="judge", role="judge", prompt=...)

        # 运行辩论
        result = await coordinator.run_debate(
            topic="Should we use microservices architecture?",
            proponent=proponent,
            opponent=opponent,
            judge=judge,
            rounds=3
        )
    """

    def __init__(
        self,
        llm_client: Any,
        model: str = "gpt-4",
        max_rounds: int = 5,
        time_limit_per_round: int = 120,  # seconds
    ):
        """
        初始化辩论协调器

        Args:
            llm_client: LLM 客户端
            model: 使用的模型
            max_rounds: 最大辩论轮数
            time_limit_per_round: 每轮时间限制（秒）
        """
        self.llm_client = llm_client
        self.model = model
        self.max_rounds = max_rounds
        self.time_limit_per_round = time_limit_per_round

        logger.info(
            f"DebateCoordinator initialized (max_rounds={max_rounds}, "
            f"time_limit={time_limit_per_round}s)"
        )

    async def run_debate(
        self,
        topic: str,
        proponent: dict,  # Agent 配置
        opponent: dict,  # Agent 配置
        judge: dict | None = None,  # 评审员配置（可选）
        rounds: int = 3,
    ) -> DebateResult:
        """
        运行辩论

        Args:
            topic: 辩论主题
            proponent: 正方 Agent
            opponent: 反方 Agent
            judge: 评审员 Agent（可选）
            rounds: 辩论轮数

        Returns:
            辩论结果
        """
        logger.info(f"Starting debate: {topic}")
        logger.info(f"Proponent: {proponent['id']}, Opponent: {opponent['id']}, Rounds: {rounds}")

        transcript = []

        # 开场陈述
        logger.info("Round 0: Opening statements")
        proponent_opening = await self._get_opening_statement(topic, proponent, "proponent")
        transcript.append(
            DebateMessage(
                round_number=0,
                agent_id=proponent["id"],
                role=DebateRole.PROPONENT,
                content=proponent_opening,
                argument_type="claim",
                timestamp=0.0,
            )
        )

        opponent_opening = await self._get_opening_statement(topic, opponent, "opponent")
        transcript.append(
            DebateMessage(
                round_number=0,
                agent_id=opponent["id"],
                role=DebateRole.OPPONENT,
                content=opponent_opening,
                argument_type="claim",
                timestamp=0.0,
            )
        )

        # 辩论轮次
        for round_num in range(1, rounds + 1):
            logger.info(f"Round {round_num}: Arguments and rebuttals")

            # 正方论证
            proponent_arg = await self._get_argument(
                topic, proponent, transcript, "proponent"
            )
            transcript.append(
                DebateMessage(
                    round_number=round_num,
                    agent_id=proponent["id"],
                    role=DebateRole.PROPONENT,
                    content=proponent_arg,
                    argument_type="argument",
                    timestamp=0.0,
                )
            )

            # 反方反驳
            opponent_rebuttal = await self._get_rebuttal(
                topic, opponent, transcript, "opponent"
            )
            transcript.append(
                DebateMessage(
                    round_number=round_num,
                    agent_id=opponent["id"],
                    role=DebateRole.OPPONENT,
                    content=opponent_rebuttal,
                    argument_type="rebuttal",
                    timestamp=0.0,
                )
            )

            # 反方论证
            opponent_arg = await self._get_argument(
                topic, opponent, transcript, "opponent"
            )
            transcript.append(
                DebateMessage(
                    round_number=round_num,
                    agent_id=opponent["id"],
                    role=DebateRole.OPPONENT,
                    content=opponent_arg,
                    argument_type="argument",
                    timestamp=0.0,
                )
            )

            # 正方反驳
            proponent_rebuttal = await self._get_rebuttal(
                topic, proponent, transcript, "proponent"
            )
            transcript.append(
                DebateMessage(
                    round_number=round_num,
                    agent_id=proponent["id"],
                    role=DebateRole.PROPONENT,
                    content=proponent_rebuttal,
                    argument_type="rebuttal",
                    timestamp=0.0,
                )
            )

        # 总结陈述
        logger.info("Final round: Closing statements")
        proponent_closing = await self._get_closing_statement(topic, proponent, transcript)
        transcript.append(
            DebateMessage(
                round_number=rounds + 1,
                agent_id=proponent["id"],
                role=DebateRole.PROPONENT,
                content=proponent_closing,
                argument_type="summary",
                timestamp=0.0,
            )
        )

        opponent_closing = await self._get_closing_statement(topic, opponent, transcript)
        transcript.append(
            DebateMessage(
                round_number=rounds + 1,
                agent_id=opponent["id"],
                role=DebateRole.OPPONENT,
                content=opponent_closing,
                argument_type="summary",
                timestamp=0.0,
            )
        )

        # 评审
        if judge:
            verdict = await self._judge_debate(topic, transcript, judge)
        else:
            # 自动评审
            verdict = await self._auto_judge(topic, transcript)

        logger.info(f"Debate concluded: winner={verdict['winner']}")

        return DebateResult(
            topic=topic,
            winner=verdict["winner"],
            consensus=verdict["consensus"],
            final_score=verdict["scores"],
            transcript=transcript,
            reasoning=verdict["reasoning"],
        )

    async def _get_opening_statement(
        self, topic: str, agent: dict, stance: str
    ) -> str:
        """获取开场陈述"""
        prompt = f"""你是辩论赛的{stance}方。请针对以下辩题发表开场陈述。

辩题: {topic}

你的立场: {"支持" if stance == "proponent" else "反对"}

请发表你的开场陈述（2-3段）:
1. 明确你的立场
2. 提出核心论点
3. 概述你的论证思路

要求简洁有力，突出重点。"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.7,
        )

        return response.strip()

    async def _get_argument(
        self, topic: str, agent: dict, transcript: list[DebateMessage], stance: str
    ) -> str:
        """获取论证"""
        history = self._format_transcript(transcript)

        prompt = f"""你是辩论赛的{stance}方。请继续你的论证。

辩题: {topic}

辩论历史:
{history}

请提出新的论据和证据来支持你的立场。要求:
1. 逻辑清晰
2. 有具体例子或数据
3. 针对对方的弱点

发表你的论证（1-2段）:"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.7,
        )

        return response.strip()

    async def _get_rebuttal(
        self, topic: str, agent: dict, transcript: list[DebateMessage], stance: str
    ) -> str:
        """获取反驳"""
        # 获取对方最近的论点
        opponent_last_arg = transcript[-1].content

        prompt = f"""你是辩论赛的{stance}方。请反驳对方的论点。

辩题: {topic}

对方刚才的论点:
{opponent_last_arg}

请反驳对方的论点。要求:
1. 指出对方论证的漏洞
2. 提供反例或反证据
3. 强化自己的立场

发表你的反驳（1-2段）:"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.7,
        )

        return response.strip()

    async def _get_closing_statement(
        self, topic: str, agent: dict, transcript: list[DebateMessage]
    ) -> str:
        """获取总结陈述"""
        history = self._format_transcript(transcript)

        prompt = f"""你是辩论赛的一方。请发表总结陈述。

辩题: {topic}

辩论历史:
{history}

请发表你的总结陈述（2-3段）:
1. 回顾你的核心论点
2. 总结你的优势论据
3. 呼吁评审支持你的立场

要求有感染力，言简意赅。"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.7,
        )

        return response.strip()

    async def _judge_debate(
        self, topic: str, transcript: list[DebateMessage], judge: dict
    ) -> dict:
        """使用评审员评判"""
        history = self._format_transcript(transcript)

        prompt = f"""你是辩论赛的评审员。请评判以下辩论。

辩题: {topic}

辩论记录:
{history}

请以 JSON 格式输出你的评判:
{{
  "winner": "proponent|opponent|tie",
  "scores": {{"proponent": 0-100, "opponent": 0-100}},
  "reasoning": "评判理由（3-5点）",
  "consensus": "综合双方观点后的共识或结论"
}}

评判标准:
1. 论证的逻辑性和完整性
2. 证据的充分性和可信度
3. 反驳的有效性
4. 陈述的说服力"""

        response = await self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        return response  # 假设返回 JSON

    async def _auto_judge(
        self, topic: str, transcript: list[DebateMessage]
    ) -> dict:
        """自动评审（无评审员时）"""
        # 简化实现：统计论据数量和质量
        proponent_args = [m for m in transcript if m.role == DebateRole.PROPONENT]
        opponent_args = [m for m in transcript if m.role == DebateRole.OPPONENT]

        proponent_score = len(proponent_args) * 10  # 简单计分
        opponent_score = len(opponent_args) * 10

        if proponent_score > opponent_score:
            winner = "proponent"
        elif opponent_score > proponent_score:
            winner = "opponent"
        else:
            winner = "tie"

        return {
            "winner": winner,
            "scores": {"proponent": proponent_score, "opponent": opponent_score},
            "reasoning": "Auto-judged based on argument count",
            "consensus": "需要人工评审以达成更准确的结论",
        }

    def _format_transcript(self, transcript: list[DebateMessage]) -> str:
        """格式化辩论记录"""
        lines = []
        for msg in transcript:
            role_name = "正方" if msg.role == DebateRole.PROPONENT else "反方"
            lines.append(f"[第{msg.round_number}轮] {role_name}: {msg.content}")
        return "\n\n".join(lines)

