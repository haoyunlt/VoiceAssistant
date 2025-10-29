"""
人类询问模块

Agent 在不确定时主动询问人类，暂停执行等待响应。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class InquiryType(Enum):
    """询问类型"""

    CLARIFICATION = "clarification"  # 澄清需求
    CHOICE = "choice"  # 选择题
    CONFIRMATION = "confirmation"  # 确认
    OPEN_ENDED = "open_ended"  # 开放式问题


class InquiryStatus(Enum):
    """询问状态"""

    PENDING = "pending"  # 等待响应
    ANSWERED = "answered"  # 已回答
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 已取消


@dataclass
class InquiryRequest:
    """询问请求"""

    inquiry_id: str
    agent_id: str
    task_id: str
    inquiry_type: InquiryType
    question: str
    options: list[str] | None  # 选项（用于选择题）
    default_answer: str | None  # 默认答案（超时时使用）
    timeout_seconds: int
    context: dict[str, Any]  # 上下文信息
    created_at: datetime


@dataclass
class InquiryResponse:
    """询问响应"""

    inquiry_id: str
    answer: str
    confidence: float  # 人类回答的置信度（可选）
    reasoning: str | None  # 回答理由
    responded_at: datetime


class HumanInquiry:
    """
    人类询问管理器

    用法:
        inquiry = HumanInquiry(websocket_manager)

        # Agent 询问人类
        answer = await inquiry.ask_human(
            agent_id="agent_001",
            task_id="task_123",
            question="Should I delete this file?",
            options=["Yes", "No", "Skip"],
            timeout_seconds=300
        )
    """

    def __init__(
        self,
        websocket_manager: Any,  # WebSocket 连接管理器
        default_timeout: int = 300,  # 5 minutes
        storage: Any | None = None,  # 用于持久化询问记录
    ):
        """
        初始化人类询问管理器

        Args:
            websocket_manager: WebSocket 管理器（用于实时通信）
            default_timeout: 默认超时时间（秒）
            storage: 存储后端（Redis/PostgreSQL）
        """
        self.websocket_manager = websocket_manager
        self.default_timeout = default_timeout
        self.storage = storage

        # 待处理的询问（内存）
        self.pending_inquiries: dict[str, InquiryRequest] = {}

        # 响应队列
        self.response_futures: dict[str, asyncio.Future] = {}

        logger.info(f"HumanInquiry initialized (default_timeout={default_timeout}s)")

    async def ask_human(
        self,
        agent_id: str,
        task_id: str,
        question: str,
        inquiry_type: InquiryType = InquiryType.OPEN_ENDED,
        options: list[str] | None = None,
        default_answer: str | None = None,
        timeout_seconds: int | None = None,
        context: dict | None = None,
    ) -> str:
        """
        询问人类

        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            question: 问题
            inquiry_type: 询问类型
            options: 选项（用于选择题）
            default_answer: 默认答案（超时时使用）
            timeout_seconds: 超时时间
            context: 上下文信息

        Returns:
            人类的回答
        """
        inquiry_id = f"inquiry_{agent_id}_{task_id}_{datetime.now().timestamp()}"
        timeout = timeout_seconds or self.default_timeout

        # 创建询问请求
        request = InquiryRequest(
            inquiry_id=inquiry_id,
            agent_id=agent_id,
            task_id=task_id,
            inquiry_type=inquiry_type,
            question=question,
            options=options,
            default_answer=default_answer,
            timeout_seconds=timeout,
            context=context or {},
            created_at=datetime.now(),
        )

        # 保存到待处理列表
        self.pending_inquiries[inquiry_id] = request

        # 创建响应 Future
        response_future = asyncio.Future()
        self.response_futures[inquiry_id] = response_future

        # 发送到前端（通过 WebSocket）
        await self._send_to_frontend(request)

        logger.info(
            f"[{inquiry_id}] Inquiry sent: {question[:50]}... (timeout={timeout}s)"
        )

        # 等待响应或超时
        try:
            answer = await asyncio.wait_for(response_future, timeout=timeout)
            logger.info(f"[{inquiry_id}] Received answer: {answer[:50]}...")
            return answer

        except TimeoutError:
            logger.warning(f"[{inquiry_id}] Timeout, using default answer")
            # 使用默认答案
            if default_answer:
                return default_answer
            else:
                raise TimeoutError(f"Human inquiry timed out: {inquiry_id}")

        finally:
            # 清理
            self.pending_inquiries.pop(inquiry_id, None)
            self.response_futures.pop(inquiry_id, None)

    async def submit_answer(
        self,
        inquiry_id: str,
        answer: str,
        confidence: float = 1.0,
        reasoning: str | None = None,
    ):
        """
        提交答案（由前端调用）

        Args:
            inquiry_id: 询问 ID
            answer: 答案
            confidence: 置信度
            reasoning: 理由
        """
        if inquiry_id not in self.response_futures:
            logger.warning(f"Inquiry {inquiry_id} not found or already answered")
            return

        # 创建响应
        response = InquiryResponse(
            inquiry_id=inquiry_id,
            answer=answer,
            confidence=confidence,
            reasoning=reasoning,
            responded_at=datetime.now(),
        )

        # 存储响应（可选）
        if self.storage:
            await self._store_response(response)

        # 设置 Future 结果
        future = self.response_futures.get(inquiry_id)
        if future and not future.done():
            future.set_result(answer)

        logger.info(f"[{inquiry_id}] Answer submitted: {answer[:50]}...")

    async def cancel_inquiry(self, inquiry_id: str):
        """取消询问"""
        if inquiry_id in self.response_futures:
            future = self.response_futures[inquiry_id]
            if not future.done():
                future.cancel()

            self.pending_inquiries.pop(inquiry_id, None)
            self.response_futures.pop(inquiry_id, None)

            logger.info(f"[{inquiry_id}] Inquiry cancelled")

    async def _send_to_frontend(self, request: InquiryRequest):
        """发送询问到前端（通过 WebSocket）"""
        try:
            message = {
                "type": "human_inquiry",
                "inquiry_id": request.inquiry_id,
                "question": request.question,
                "inquiry_type": request.inquiry_type.value,
                "options": request.options,
                "timeout_seconds": request.timeout_seconds,
                "context": request.context,
            }

            # 发送到对应的任务/会话的 WebSocket 连接
            await self.websocket_manager.send_to_task(request.task_id, message)

        except Exception as e:
            logger.error(f"Error sending inquiry to frontend: {e}")

    async def _store_response(self, response: InquiryResponse):
        """存储响应到数据库"""
        try:
            if hasattr(self.storage, "store_inquiry_response"):
                await self.storage.store_inquiry_response(
                    inquiry_id=response.inquiry_id,
                    answer=response.answer,
                    confidence=response.confidence,
                    reasoning=response.reasoning,
                    responded_at=response.responded_at,
                )
        except Exception as e:
            logger.error(f"Error storing response: {e}")

    async def get_pending_inquiries(self, task_id: str | None = None) -> list[InquiryRequest]:
        """获取待处理的询问"""
        if task_id:
            return [req for req in self.pending_inquiries.values() if req.task_id == task_id]
        else:
            return list(self.pending_inquiries.values())

    async def batch_ask(
        self,
        agent_id: str,
        task_id: str,
        questions: list[dict[str, Any]],
    ) -> list[str]:
        """
        批量询问

        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            questions: 问题列表，每个问题是一个字典，包含 question, options 等

        Returns:
            答案列表
        """
        tasks = []
        for q in questions:
            task = self.ask_human(
                agent_id=agent_id,
                task_id=task_id,
                question=q["question"],
                inquiry_type=InquiryType(q.get("type", "open_ended")),
                options=q.get("options"),
                default_answer=q.get("default_answer"),
                timeout_seconds=q.get("timeout_seconds"),
                context=q.get("context"),
            )
            tasks.append(task)

        # 并发执行
        answers = await asyncio.gather(*tasks)
        return answers


class FeedbackLearning:
    """
    人类反馈学习

    记录和分析人类干预，用于改进 Agent。
    """

    def __init__(self, storage: Any):
        """
        初始化反馈学习

        Args:
            storage: 存储后端
        """
        self.storage = storage
        logger.info("FeedbackLearning initialized")

    async def record_correction(
        self,
        agent_id: str,
        task_id: str,
        original_action: str,
        corrected_action: str,
        reasoning: str | None = None,
    ):
        """
        记录人类修正

        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            original_action: 原始动作
            corrected_action: 修正后的动作
            reasoning: 修正理由
        """
        correction = {
            "agent_id": agent_id,
            "task_id": task_id,
            "original_action": original_action,
            "corrected_action": corrected_action,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        }

        await self.storage.store_correction(correction)
        logger.info(f"Recorded correction for agent {agent_id}")

    async def record_rejection(
        self,
        agent_id: str,
        task_id: str,
        rejected_action: str,
        reasoning: str | None = None,
    ):
        """
        记录人类拒绝

        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            rejected_action: 被拒绝的动作
            reasoning: 拒绝理由
        """
        rejection = {
            "agent_id": agent_id,
            "task_id": task_id,
            "rejected_action": rejected_action,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        }

        await self.storage.store_rejection(rejection)
        logger.info(f"Recorded rejection for agent {agent_id}")

    async def get_feedback_summary(self, agent_id: str, days: int = 7) -> dict:
        """
        获取反馈摘要

        Args:
            agent_id: Agent ID
            days: 天数

        Returns:
            摘要统计
        """
        corrections = await self.storage.get_corrections(agent_id, days)
        rejections = await self.storage.get_rejections(agent_id, days)

        return {
            "agent_id": agent_id,
            "correction_count": len(corrections),
            "rejection_count": len(rejections),
            "total_feedback": len(corrections) + len(rejections),
            "corrections": corrections[:10],  # 最近 10 条
            "rejections": rejections[:10],  # 最近 10 条
        }

    async def generate_improvement_suggestions(self, agent_id: str) -> list[str]:
        """
        生成改进建议（基于反馈）

        Args:
            agent_id: Agent ID

        Returns:
            改进建议列表
        """
        summary = await self.get_feedback_summary(agent_id, days=30)

        suggestions = []

        if summary["correction_count"] > 10:
            suggestions.append(
                f"检测到 {summary['correction_count']} 次修正，建议分析常见错误模式"
            )

        if summary["rejection_count"] > 5:
            suggestions.append(
                f"检测到 {summary['rejection_count']} 次拒绝，建议增强决策审慎性"
            )

        # 分析具体类别
        # （实际项目中可以使用 LLM 分析反馈文本）

        return suggestions

