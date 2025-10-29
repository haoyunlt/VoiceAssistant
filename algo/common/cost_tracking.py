"""
请求级成本追踪

实现 "请求级 Token 计费"功能，支持：
- Token使用追踪（prompt + completion + embedding）
- 成本计算（基于模型定价）
- 预算告警
- 多维度归因（tenant/user/model）
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# 模型定价表（美元/1K tokens）
MODEL_PRICING = {
    # OpenAI
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4-turbo-preview": {"prompt": 0.01, "completion": 0.03},
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
    # Anthropic
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    # Embedding models
    "text-embedding-3-large": {"embedding": 0.00013},
    "text-embedding-3-small": {"embedding": 0.00002},
    "text-embedding-ada-002": {"embedding": 0.0001},
    # BGE
    "bge-m3": {"embedding": 0.0},  # 本地部署，无成本
    "bge-large-zh": {"embedding": 0.0},
}


@dataclass
class CostContext:
    """
    请求成本上下文

    使用 contextvars 实现请求级隔离，在异步环境中自动传递
    """

    request_id: str
    tenant_id: str | None = None
    user_id: str | None = None

    # Token使用统计
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    total_tokens: int = 0

    # 调用次数统计
    llm_calls: int = 0
    embedding_calls: int = 0
    retrieval_calls: int = 0
    rerank_calls: int = 0

    # 时间统计
    start_time: float = field(default_factory=time.time)
    llm_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0

    # 成本估算（美元）
    estimated_cost_usd: float = 0.0

    # 模型使用详情
    models_used: dict[str, int] = field(default_factory=dict)  # model_name -> call_count


# 使用 ContextVar 存储请求上下文
_cost_context_var: ContextVar[CostContext | None] = ContextVar("cost_context", default=None)


def get_cost_context() -> CostContext | None:
    """
    获取当前请求的成本上下文

    Returns:
        CostContext 实例，如果未设置则返回 None
    """
    return _cost_context_var.get()


def set_cost_context(context: CostContext) -> None:
    """
    设置成本上下文

    Args:
        context: CostContext 实例
    """
    _cost_context_var.set(context)


def clear_cost_context() -> None:
    """清除成本上下文"""
    _cost_context_var.set(None)


def track_llm_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
) -> None:
    """
    追踪 LLM 使用

    Args:
        model: 模型名称
        prompt_tokens: Prompt token 数量
        completion_tokens: Completion token 数量
        latency_ms: 调用延迟（毫秒）
    """
    context = get_cost_context()
    if not context:
        logger.warning("No cost context found, LLM usage not tracked")
        return

    # 更新统计
    context.prompt_tokens += prompt_tokens
    context.completion_tokens += completion_tokens
    context.total_tokens += prompt_tokens + completion_tokens
    context.llm_calls += 1
    context.llm_latency_ms += latency_ms

    # 记录模型使用
    context.models_used[model] = context.models_used.get(model, 0) + 1

    # 计算成本
    pricing = MODEL_PRICING.get(model)
    if pricing:
        prompt_cost = (prompt_tokens / 1000) * pricing.get("prompt", 0)
        completion_cost = (completion_tokens / 1000) * pricing.get("completion", 0)
        cost = prompt_cost + completion_cost
        context.estimated_cost_usd += cost

        logger.debug(
            f"LLM usage tracked: model={model}, "
            f"tokens=({prompt_tokens}+{completion_tokens}), "
            f"cost=${cost:.6f}"
        )
    else:
        logger.warning(f"Pricing not found for model: {model}")


def track_embedding_usage(
    model: str,
    tokens: int,
    latency_ms: float,  # noqa: ARG001 - reserved for future metrics
) -> None:
    """
    追踪 Embedding 使用

    Args:
        model: Embedding 模型名称
        tokens: Token 数量
        latency_ms: 调用延迟（毫秒）
    """
    context = get_cost_context()
    if not context:
        logger.warning("No cost context found, embedding usage not tracked")
        return

    context.embedding_tokens += tokens
    context.total_tokens += tokens
    context.embedding_calls += 1

    # 记录模型使用
    context.models_used[model] = context.models_used.get(model, 0) + 1

    # 计算成本
    pricing = MODEL_PRICING.get(model)
    if pricing and "embedding" in pricing:
        cost = (tokens / 1000) * pricing["embedding"]
        context.estimated_cost_usd += cost

        logger.debug(f"Embedding usage tracked: model={model}, tokens={tokens}, cost=${cost:.6f}")


def track_retrieval_call(latency_ms: float) -> None:
    """
    追踪检索调用

    Args:
        latency_ms: 调用延迟（毫秒）
    """
    context = get_cost_context()
    if not context:
        return

    context.retrieval_calls += 1
    context.retrieval_latency_ms += latency_ms


def track_rerank_call() -> None:
    """追踪重排序调用"""
    context = get_cost_context()
    if not context:
        return

    context.rerank_calls += 1


def get_cost_summary() -> dict | None:
    """
    获取成本摘要

    Returns:
        成本摘要字典，包含所有统计信息
    """
    context = get_cost_context()
    if not context:
        return None

    duration_s = time.time() - context.start_time

    return {
        "request_id": context.request_id,
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        # Token统计
        "tokens": {
            "prompt": context.prompt_tokens,
            "completion": context.completion_tokens,
            "embedding": context.embedding_tokens,
            "total": context.total_tokens,
        },
        # 调用统计
        "calls": {
            "llm": context.llm_calls,
            "embedding": context.embedding_calls,
            "retrieval": context.retrieval_calls,
            "rerank": context.rerank_calls,
        },
        # 延迟统计
        "latency_ms": {
            "llm": context.llm_latency_ms,
            "retrieval": context.retrieval_latency_ms,
            "total": duration_s * 1000,
        },
        # 成本
        "cost_usd": round(context.estimated_cost_usd, 6),
        # 模型使用
        "models": context.models_used,
        # 时间
        "duration_s": round(duration_s, 3),
    }


# FastAPI 中间件
async def cost_tracking_middleware(request, call_next):  # type: ignore[no-untyped-def]
    """
    成本追踪中间件

    在每个请求开始时创建 CostContext，请求结束时记录日志

    Usage:
        from fastapi import FastAPI
        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=cost_tracking_middleware)
    """
    import uuid

    # 创建成本上下文
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)

    context = CostContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    set_cost_context(context)

    try:
        response = await call_next(request)

        # 记录成本日志
        summary = get_cost_summary()
        if summary:
            logger.info(
                "Request cost summary",
                extra={
                    "event": "request_cost",
                    **summary,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                },
            )

            # 添加成本信息到响应头（可选）
            response.headers["X-Request-ID"] = context.request_id
            response.headers["X-Total-Tokens"] = str(context.total_tokens)
            response.headers["X-Estimated-Cost-USD"] = f"{context.estimated_cost_usd:.6f}"
            response.headers["X-LLM-Calls"] = str(context.llm_calls)

        return response

    finally:
        clear_cost_context()


# 预算告警检查
class BudgetAlert:
    """预算告警"""

    def __init__(self, daily_limit_usd: float = 1000.0):
        """
        初始化预算告警

        Args:
            daily_limit_usd: 日成本上限（美元）
        """
        self.daily_limit_usd = daily_limit_usd
        self.daily_cost = 0.0
        self.last_reset = time.time()

    def check_and_update(self, cost_usd: float) -> bool:
        """
        检查并更新预算

        Args:
            cost_usd: 当前请求成本

        Returns:
            是否超出预算
        """
        # 每天重置
        current_time = time.time()
        if current_time - self.last_reset > 86400:  # 24小时
            self.daily_cost = 0.0
            self.last_reset = current_time

        self.daily_cost += cost_usd

        if self.daily_cost > self.daily_limit_usd:
            logger.error(
                f"Daily budget exceeded: ${self.daily_cost:.2f} / ${self.daily_limit_usd:.2f}"
            )
            return True

        # 预警阈值（90%）
        if self.daily_cost > self.daily_limit_usd * 0.9:
            logger.warning(
                f"Daily budget warning: ${self.daily_cost:.2f} / ${self.daily_limit_usd:.2f} "
                f"({self.daily_cost / self.daily_limit_usd * 100:.1f}%)"
            )

        return False
