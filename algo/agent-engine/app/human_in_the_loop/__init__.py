"""
人机协作 (Human-in-the-Loop) 模块

包含人类询问、审批流程、反馈学习等功能。
"""

from app.human_in_the_loop.approval import ApprovalWorkflow
from app.human_in_the_loop.inquiry import HumanInquiry

__all__ = [
    "HumanInquiry",
    "ApprovalWorkflow",
]
