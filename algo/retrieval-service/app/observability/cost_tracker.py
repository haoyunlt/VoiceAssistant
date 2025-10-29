"""
Cost Tracking & Budgeting - 成本追踪与预算管理

功能:
- 请求级成本追踪
- 租户/模块成本聚合
- 预算告警和自动降级

成本项:
- LLM调用 (token based)
- Embedding生成 (per request)
- Reranking (per document)
- 缓存存储 (per GB/day)
- 向量检索 (per request)
"""

import time
from dataclasses import dataclass, field

from app.core.logging import logger


@dataclass
class CostItem:
    """成本条目"""

    service: str  # llm, embedding, rerank, cache, vector
    quantity: float  # tokens, requests, documents等
    unit_price: float  # 单价
    cost: float  # 总成本
    timestamp: float = field(default_factory=time.time)


@dataclass
class RequestCost:
    """请求成本"""

    request_id: str
    tenant_id: str
    operation: str  # hybrid_search, vector_search, etc.
    items: list[CostItem]
    total_cost: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class BudgetAlert:
    """预算告警"""

    tenant_id: str
    budget_limit: float
    current_spend: float
    utilization: float  # 使用率
    alert_level: str  # warning, critical
    timestamp: float = field(default_factory=time.time)


class CostTracker:
    """成本追踪器"""

    # 成本配置 (美元)
    PRICES = {
        "llm_input_token": 0.0000015,  # $1.5 per 1M tokens
        "llm_output_token": 0.000002,  # $2 per 1M tokens
        "embedding_request": 0.0001,  # $0.1 per 1K requests
        "rerank_document": 0.00001,  # $0.01 per 1K documents
        "vector_search": 0.00001,  # $0.01 per 1K searches
        "cache_gb_day": 0.02,  # $0.02 per GB per day
    }

    def __init__(self):
        """初始化成本追踪器"""
        self.request_costs: list[RequestCost] = []
        self.tenant_budgets: dict[str, float] = {}  # tenant_id -> budget limit
        self.tenant_spends: dict[str, float] = {}  # tenant_id -> current spend

        logger.info("Cost tracker initialized")

    def track_request(
        self,
        request_id: str,
        tenant_id: str,
        operation: str,
        items: list[CostItem],
    ) -> RequestCost:
        """
        追踪请求成本

        Args:
            request_id: 请求ID
            tenant_id: 租户ID
            operation: 操作类型
            items: 成本条目列表

        Returns:
            请求成本
        """
        total_cost = sum(item.cost for item in items)

        request_cost = RequestCost(
            request_id=request_id,
            tenant_id=tenant_id,
            operation=operation,
            items=items,
            total_cost=total_cost,
        )

        self.request_costs.append(request_cost)

        # 更新租户花费
        if tenant_id not in self.tenant_spends:
            self.tenant_spends[tenant_id] = 0
        self.tenant_spends[tenant_id] += total_cost

        # 检查预算
        alert = self._check_budget(tenant_id)
        if alert:
            logger.warning(
                f"Budget alert for tenant {tenant_id}: {alert.utilization * 100:.1f}% utilized"
            )

        return request_cost

    def calculate_llm_cost(self, input_tokens: int, output_tokens: int) -> CostItem:
        """计算LLM成本"""
        input_cost = input_tokens * self.PRICES["llm_input_token"]
        output_cost = output_tokens * self.PRICES["llm_output_token"]
        total_cost = input_cost + output_cost

        return CostItem(
            service="llm",
            quantity=input_tokens + output_tokens,
            unit_price=(input_cost + output_cost) / (input_tokens + output_tokens)
            if (input_tokens + output_tokens) > 0
            else 0,
            cost=total_cost,
        )

    def calculate_embedding_cost(self, num_requests: int) -> CostItem:
        """计算Embedding成本"""
        cost = num_requests * self.PRICES["embedding_request"]

        return CostItem(
            service="embedding",
            quantity=num_requests,
            unit_price=self.PRICES["embedding_request"],
            cost=cost,
        )

    def calculate_rerank_cost(self, num_documents: int) -> CostItem:
        """计算Rerank成本"""
        cost = num_documents * self.PRICES["rerank_document"]

        return CostItem(
            service="rerank",
            quantity=num_documents,
            unit_price=self.PRICES["rerank_document"],
            cost=cost,
        )

    def calculate_vector_search_cost(self, num_searches: int) -> CostItem:
        """计算向量检索成本"""
        cost = num_searches * self.PRICES["vector_search"]

        return CostItem(
            service="vector_search",
            quantity=num_searches,
            unit_price=self.PRICES["vector_search"],
            cost=cost,
        )

    def set_budget(self, tenant_id: str, budget: float):
        """
        设置租户预算

        Args:
            tenant_id: 租户ID
            budget: 预算金额（美元）
        """
        self.tenant_budgets[tenant_id] = budget
        logger.info(f"Budget set for tenant {tenant_id}: ${budget:.2f}")

    def _check_budget(self, tenant_id: str) -> BudgetAlert | None:
        """
        检查预算使用情况

        Args:
            tenant_id: 租户ID

        Returns:
            如果超过阈值，返回告警
        """
        if tenant_id not in self.tenant_budgets:
            return None

        budget_limit = self.tenant_budgets[tenant_id]
        current_spend = self.tenant_spends.get(tenant_id, 0)
        utilization = current_spend / budget_limit if budget_limit > 0 else 0

        if utilization >= 0.9:
            return BudgetAlert(
                tenant_id=tenant_id,
                budget_limit=budget_limit,
                current_spend=current_spend,
                utilization=utilization,
                alert_level="critical",
            )
        elif utilization >= 0.75:
            return BudgetAlert(
                tenant_id=tenant_id,
                budget_limit=budget_limit,
                current_spend=current_spend,
                utilization=utilization,
                alert_level="warning",
            )

        return None

    def get_tenant_summary(self, tenant_id: str) -> dict:
        """
        获取租户成本摘要

        Args:
            tenant_id: 租户ID

        Returns:
            成本摘要
        """
        tenant_requests = [rc for rc in self.request_costs if rc.tenant_id == tenant_id]

        total_spend = self.tenant_spends.get(tenant_id, 0)
        budget_limit = self.tenant_budgets.get(tenant_id, 0)
        utilization = total_spend / budget_limit if budget_limit > 0 else 0

        # 按服务聚合
        service_costs = {}
        for request_cost in tenant_requests:
            for item in request_cost.items:
                if item.service not in service_costs:
                    service_costs[item.service] = 0
                service_costs[item.service] += item.cost

        return {
            "tenant_id": tenant_id,
            "total_requests": len(tenant_requests),
            "total_spend": total_spend,
            "budget_limit": budget_limit,
            "budget_utilization": utilization,
            "service_breakdown": service_costs,
        }

    def get_global_summary(self) -> dict:
        """获取全局成本摘要"""
        total_spend = sum(self.tenant_spends.values())
        total_requests = len(self.request_costs)

        # 按服务聚合
        service_costs = {}
        for request_cost in self.request_costs:
            for item in request_cost.items:
                if item.service not in service_costs:
                    service_costs[item.service] = 0
                service_costs[item.service] += item.cost

        return {
            "total_requests": total_requests,
            "total_spend": total_spend,
            "total_tenants": len(self.tenant_spends),
            "service_breakdown": service_costs,
            "avg_cost_per_request": (total_spend / total_requests if total_requests > 0 else 0),
        }


# 全局单例
_cost_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    """获取全局成本追踪器"""
    return _cost_tracker


# 使用示例
if __name__ == "__main__":
    tracker = get_cost_tracker()

    # 设置预算
    tracker.set_budget("tenant_001", 100.0)  # $100预算

    # 追踪请求成本
    items = [
        tracker.calculate_llm_cost(input_tokens=1000, output_tokens=500),
        tracker.calculate_embedding_cost(num_requests=1),
        tracker.calculate_rerank_cost(num_documents=10),
        tracker.calculate_vector_search_cost(num_searches=1),
    ]

    request_cost = tracker.track_request(
        request_id="req_001",
        tenant_id="tenant_001",
        operation="hybrid_search",
        items=items,
    )

    print(f"Request cost: ${request_cost.total_cost:.6f}")

    # 获取摘要
    summary = tracker.get_tenant_summary("tenant_001")
    print("\nTenant summary:")
    print(f"  Total spend: ${summary['total_spend']:.6f}")
    print(f"  Budget utilization: {summary['budget_utilization'] * 100:.1f}%")
    print(f"  Service breakdown: {summary['service_breakdown']}")
