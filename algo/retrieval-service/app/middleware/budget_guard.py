"""
Budget Guard Middleware - 预算守卫中间件

功能:
- 租户预算检查
- 自动降级策略
- 90%: 禁用LLM enhancement
- 95%: 仅vector检索
- 100%: 限流

目标:
- 成本可控
- 告警及时（<1min）
"""

from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.cost_tracker import get_cost_tracker
from app.observability.logging import logger


class BudgetGuardMiddleware(BaseHTTPMiddleware):
    """预算守卫中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理请求

        Args:
            request: HTTP请求
            call_next: 下一个处理器

        Returns:
            HTTP响应
        """
        # 提取tenant_id
        tenant_id = request.headers.get("X-Tenant-ID", "default")

        # 检查预算
        cost_tracker = get_cost_tracker()
        budget_status = self._check_budget(cost_tracker, tenant_id)

        # 应用降级
        if budget_status["action"] == "rate_limit":
            return Response(
                content='{"error": "Budget exceeded, rate limited"}',
                status_code=429,
                media_type="application/json",
            )

        # 在请求状态中保存降级信息
        request.state.budget_status = budget_status
        request.state.degradation_applied = budget_status["action"] != "normal"

        # 记录降级
        if request.state.degradation_applied:
            logger.warning(
                f"Budget degradation applied for tenant {tenant_id}: "
                f"action={budget_status['action']}, "
                f"utilization={budget_status['utilization']:.1%}"
            )

        # 继续处理
        response = await call_next(request)

        # 添加预算状态头
        response.headers["X-Budget-Utilization"] = f"{budget_status['utilization']:.2f}"
        response.headers["X-Budget-Action"] = budget_status["action"]

        return response

    def _check_budget(self, cost_tracker, tenant_id: str) -> dict:
        """检查预算状态"""
        if tenant_id not in cost_tracker.tenant_budgets:
            return {"status": "no_budget", "action": "normal", "utilization": 0.0}

        budget_limit = cost_tracker.tenant_budgets[tenant_id]
        current_spend = cost_tracker.tenant_spends.get(tenant_id, 0)
        utilization = current_spend / budget_limit if budget_limit > 0 else 0

        # 降级策略
        if utilization >= 1.0:
            action = "rate_limit"
            level = "critical"
        elif utilization >= 0.95:
            action = "vector_only"
            level = "warning"
        elif utilization >= 0.90:
            action = "disable_llm"
            level = "warning"
        else:
            action = "normal"
            level = "ok"

        return {
            "status": level,
            "action": action,
            "utilization": utilization,
            "current_spend": current_spend,
            "budget_limit": budget_limit,
        }
