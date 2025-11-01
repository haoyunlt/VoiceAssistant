"""
Agent 相关 Prometheus 指标

为 Agentic RAG 提供详细的性能和质量指标
"""

import time

from prometheus_client import Counter, Gauge, Histogram

# ==================== Agent 查询指标 ====================

agent_query_total = Counter(
    "agent_query_total",
    "Agent 查询总数",
    ["tenant_id", "status"],  # status: success/error/timeout/max_iterations
)

agent_convergence_rate = Gauge(
    "agent_convergence_rate",
    "Agent 收敛成功率",
    ["tenant_id"],
)

# ==================== 迭代指标 ====================

agent_iterations_count = Histogram(
    "agent_iterations_count",
    "Agent 迭代次数分布",
    ["tenant_id"],
    buckets=[1, 2, 3, 5, 7, 10, 15],
)

agent_latency_ms = Histogram(
    "agent_latency_ms",
    "Agent 执行延迟（毫秒）",
    ["tenant_id"],
    buckets=[500, 1000, 2000, 5000, 10000, 20000, 30000],
)

# ==================== 工具调用指标 ====================

agent_tool_calls_total = Counter(
    "agent_tool_calls_total",
    "工具调用总次数",
    ["tool_name", "tenant_id", "status"],  # status: success/error
)

agent_tool_latency_ms = Histogram(
    "agent_tool_latency_ms",
    "工具执行延迟（毫秒）",
    ["tool_name", "tenant_id"],
    buckets=[10, 50, 100, 500, 1000, 5000],
)

# ==================== 错误指标 ====================

agent_errors_total = Counter(
    "agent_errors_total",
    "Agent 错误总数",
    ["error_type", "tenant_id"],  # error_type: timeout/max_iterations/tool_error/llm_error
)

# ==================== 辅助函数 ====================


def record_agent_query(tenant_id: str, status: str):
    """记录 Agent 查询"""
    agent_query_total.labels(tenant_id=tenant_id, status=status).inc()


def record_agent_iterations(tenant_id: str, iterations: int):
    """记录迭代次数"""
    agent_iterations_count.labels(tenant_id=tenant_id).observe(iterations)


def record_agent_latency(tenant_id: str, latency_ms: float):
    """记录 Agent 延迟"""
    agent_latency_ms.labels(tenant_id=tenant_id).observe(latency_ms)


def record_tool_call(tool_name: str, tenant_id: str, status: str):
    """记录工具调用"""
    agent_tool_calls_total.labels(tool_name=tool_name, tenant_id=tenant_id, status=status).inc()


def record_tool_latency(tool_name: str, tenant_id: str, latency_ms: float):
    """记录工具延迟"""
    agent_tool_latency_ms.labels(tool_name=tool_name, tenant_id=tenant_id).observe(latency_ms)


def record_agent_error(error_type: str, tenant_id: str):
    """记录 Agent 错误"""
    agent_errors_total.labels(error_type=error_type, tenant_id=tenant_id).inc()


class AgentMetrics:
    """Agent 指标收集器（上下文管理器）"""

    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self.start_time = None
        self.iterations = 0
        self.tool_calls = []

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency_ms = (time.time() - self.start_time) * 1000
            record_agent_latency(self.tenant_id, latency_ms)

            # 记录状态
            if exc_type:
                if exc_type.__name__ == "TimeoutError":
                    status = "timeout"
                    record_agent_error("timeout", self.tenant_id)
                elif exc_type.__name__ == "MaxIterationsError":
                    status = "max_iterations"
                    record_agent_error("max_iterations", self.tenant_id)
                else:
                    status = "error"
                    record_agent_error(exc_type.__name__, self.tenant_id)
            else:
                status = "success"

            record_agent_query(self.tenant_id, status)

            # 记录迭代次数
            if self.iterations > 0:
                record_agent_iterations(self.tenant_id, self.iterations)

    def record_iteration(self):
        """记录一次迭代"""
        self.iterations += 1

    def record_tool_call_metric(self, tool_name: str, latency_ms: float, success: bool = True):
        """记录工具调用"""
        status = "success" if success else "error"
        record_tool_call(tool_name, self.tenant_id, status)
        record_tool_latency(tool_name, self.tenant_id, latency_ms)
        self.tool_calls.append({"tool": tool_name, "latency": latency_ms, "success": success})


# 导出所有指标
agent_metrics = {
    "query_total": agent_query_total,
    "convergence_rate": agent_convergence_rate,
    "iterations_count": agent_iterations_count,
    "latency_ms": agent_latency_ms,
    "tool_calls_total": agent_tool_calls_total,
    "tool_latency_ms": agent_tool_latency_ms,
    "errors_total": agent_errors_total,
}
