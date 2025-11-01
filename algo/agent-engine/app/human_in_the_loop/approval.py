"""
审批流程模块

高风险操作需要人类审批才能执行。
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ActionRiskLevel(Enum):
    """操作风险等级"""

    LOW = "low"  # 低风险，无需审批
    MEDIUM = "medium"  # 中风险，建议审批
    HIGH = "high"  # 高风险，必须审批
    CRITICAL = "critical"  # 严重风险，需要多级审批


class ApprovalStatus(Enum):
    """审批状态"""

    PENDING = "pending"  # 等待审批
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 已取消


@dataclass
class ApprovalRequest:
    """审批请求"""

    approval_id: str
    agent_id: str
    task_id: str
    action_type: str  # "delete", "send_email", "api_call", etc.
    action_details: dict[str, Any]
    risk_level: ActionRiskLevel
    reasoning: str  # Agent 的理由
    timeout_seconds: int
    created_at: datetime


@dataclass
class ApprovalDecision:
    """审批决策"""

    approval_id: str
    status: ApprovalStatus
    approver_id: str  # 审批人 ID
    reasoning: str | None  # 审批理由
    decided_at: datetime


class ApprovalWorkflow:
    """
    审批流程管理器

    用法:
        workflow = ApprovalWorkflow(websocket_manager, risk_rules)

        # Agent 请求审批
        is_approved = await workflow.request_approval(
            agent_id="agent_001",
            task_id="task_123",
            action_type="delete_file",
            action_details={"file_path": "/important/data.txt"}
        )

        if is_approved:
            # 执行操作
            pass
    """

    def __init__(
        self,
        websocket_manager: Any,
        risk_rules: dict | None = None,
        default_timeout: int = 300,
        storage: Any | None = None,
    ):
        """
        初始化审批流程管理器

        Args:
            websocket_manager: WebSocket 管理器
            risk_rules: 风险规则配置
            default_timeout: 默认超时时间（秒）
            storage: 存储后端
        """
        self.websocket_manager = websocket_manager
        self.risk_rules = risk_rules or self._default_risk_rules()
        self.default_timeout = default_timeout
        self.storage = storage

        # 待审批列表
        self.pending_approvals: dict[str, ApprovalRequest] = {}

        # 审批结果 Future
        self.approval_futures: dict[str, asyncio.Future] = {}

        logger.info(f"ApprovalWorkflow initialized (default_timeout={default_timeout}s)")

    def _default_risk_rules(self) -> dict:
        """默认风险规则"""
        return {
            # 高风险操作
            "delete": ActionRiskLevel.HIGH,
            "drop_table": ActionRiskLevel.CRITICAL,
            "send_email": ActionRiskLevel.HIGH,
            "send_message": ActionRiskLevel.MEDIUM,
            "api_call": ActionRiskLevel.MEDIUM,
            # 金额操作
            "payment": ActionRiskLevel.CRITICAL,
            "refund": ActionRiskLevel.HIGH,
            # 数据操作
            "export_data": ActionRiskLevel.HIGH,
            "modify_user": ActionRiskLevel.MEDIUM,
        }

    async def request_approval(
        self,
        agent_id: str,
        task_id: str,
        action_type: str,
        action_details: dict[str, Any],
        reasoning: str | None = None,
        timeout_seconds: int | None = None,
    ) -> bool:
        """
        请求审批

        Args:
            agent_id: Agent ID
            task_id: 任务 ID
            action_type: 操作类型
            action_details: 操作详情
            reasoning: Agent 的理由
            timeout_seconds: 超时时间

        Returns:
            是否批准（True/False）
        """
        # 评估风险等级
        risk_level = self._assess_risk(action_type, action_details)

        # 低风险操作，自动批准
        if risk_level == ActionRiskLevel.LOW:
            logger.info(f"Action {action_type} is low risk, auto-approved")
            return True

        approval_id = f"approval_{agent_id}_{task_id}_{datetime.now().timestamp()}"
        timeout = timeout_seconds or self.default_timeout

        # 创建审批请求
        request = ApprovalRequest(
            approval_id=approval_id,
            agent_id=agent_id,
            task_id=task_id,
            action_type=action_type,
            action_details=action_details,
            risk_level=risk_level,
            reasoning=reasoning or "Agent requested approval",
            timeout_seconds=timeout,
            created_at=datetime.now(),
        )

        # 保存到待审批列表
        self.pending_approvals[approval_id] = request

        # 创建审批 Future
        approval_future = asyncio.Future()
        self.approval_futures[approval_id] = approval_future

        # 发送到前端
        await self._send_to_frontend(request)

        logger.info(
            f"[{approval_id}] Approval request sent: {action_type} (risk={risk_level.value})"
        )

        # 等待审批或超时
        try:
            is_approved = await asyncio.wait_for(approval_future, timeout=timeout)
            return is_approved

        except TimeoutError:
            logger.warning(f"[{approval_id}] Approval timeout, rejecting by default")
            # 超时默认拒绝
            return False

        finally:
            # 清理
            self.pending_approvals.pop(approval_id, None)
            self.approval_futures.pop(approval_id, None)

    async def submit_decision(
        self,
        approval_id: str,
        is_approved: bool,
        approver_id: str,
        reasoning: str | None = None,
    ):
        """
        提交审批决策（由前端调用）

        Args:
            approval_id: 审批 ID
            is_approved: 是否批准
            approver_id: 审批人 ID
            reasoning: 审批理由
        """
        if approval_id not in self.approval_futures:
            logger.warning(f"Approval {approval_id} not found or already decided")
            return

        # 创建决策
        decision = ApprovalDecision(
            approval_id=approval_id,
            status=ApprovalStatus.APPROVED if is_approved else ApprovalStatus.REJECTED,
            approver_id=approver_id,
            reasoning=reasoning,
            decided_at=datetime.now(),
        )

        # 存储决策
        if self.storage:
            await self._store_decision(decision)

        # 设置 Future 结果
        future = self.approval_futures.get(approval_id)
        if future and not future.done():
            future.set_result(is_approved)

        logger.info(
            f"[{approval_id}] Decision submitted: "
            f"{'APPROVED' if is_approved else 'REJECTED'} by {approver_id}"
        )

    def _assess_risk(self, action_type: str, action_details: dict) -> ActionRiskLevel:
        """评估风险等级"""
        # 基础风险（从规则表）
        base_risk = self.risk_rules.get(action_type, ActionRiskLevel.MEDIUM)

        # 根据详情调整风险
        # 例如：金额操作根据金额大小调整风险
        if action_type in ["payment", "refund"]:
            amount = action_details.get("amount", 0)
            if amount > 10000:
                return ActionRiskLevel.CRITICAL
            elif amount > 1000:
                return ActionRiskLevel.HIGH

        # 删除操作根据路径调整风险
        if action_type == "delete":
            path = action_details.get("file_path", "")
            if "/system" in path or "/root" in path:
                return ActionRiskLevel.CRITICAL

        return base_risk

    async def _send_to_frontend(self, request: ApprovalRequest):
        """发送审批请求到前端"""
        try:
            message = {
                "type": "approval_request",
                "approval_id": request.approval_id,
                "action_type": request.action_type,
                "action_details": request.action_details,
                "risk_level": request.risk_level.value,
                "reasoning": request.reasoning,
                "timeout_seconds": request.timeout_seconds,
            }

            await self.websocket_manager.send_to_task(request.task_id, message)

        except Exception as e:
            logger.error(f"Error sending approval request to frontend: {e}")

    async def _store_decision(self, decision: ApprovalDecision):
        """存储审批决策"""
        try:
            if hasattr(self.storage, "store_approval_decision"):
                await self.storage.store_approval_decision(
                    approval_id=decision.approval_id,
                    status=decision.status.value,
                    approver_id=decision.approver_id,
                    reasoning=decision.reasoning,
                    decided_at=decision.decided_at,
                )
        except Exception as e:
            logger.error(f"Error storing decision: {e}")

    async def get_pending_approvals(self, task_id: str | None = None) -> list[ApprovalRequest]:
        """获取待审批列表"""
        if task_id:
            return [req for req in self.pending_approvals.values() if req.task_id == task_id]
        else:
            return list(self.pending_approvals.values())

    async def cancel_approval(self, approval_id: str):
        """取消审批"""
        if approval_id in self.approval_futures:
            future = self.approval_futures[approval_id]
            if not future.done():
                future.cancel()

            self.pending_approvals.pop(approval_id, None)
            self.approval_futures.pop(approval_id, None)

            logger.info(f"[{approval_id}] Approval cancelled")

    async def get_approval_history(self, agent_id: str | None = None, days: int = 7) -> list[dict]:
        """获取审批历史"""
        if self.storage and hasattr(self.storage, "get_approval_history"):
            return await self.storage.get_approval_history(agent_id, days)
        else:
            return []

    async def get_approval_stats(self, agent_id: str, days: int = 30) -> dict:
        """获取审批统计"""
        history = await self.get_approval_history(agent_id, days)

        total = len(history)
        approved = sum(1 for h in history if h["status"] == "approved")
        rejected = sum(1 for h in history if h["status"] == "rejected")
        timeout = sum(1 for h in history if h["status"] == "timeout")

        return {
            "agent_id": agent_id,
            "total_requests": total,
            "approved": approved,
            "rejected": rejected,
            "timeout": timeout,
            "approval_rate": approved / total if total > 0 else 0.0,
        }
