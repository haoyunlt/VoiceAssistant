"""
Agent Execution Tracer - 执行追踪器

功能:
- 记录 Agent 执行的每个步骤（Thought, Action, Observation）
- 支持嵌套子任务追踪（Plan-Execute 模式）
- 生成工具调用时序图和依赖关系
- 导出追踪数据到 OpenTelemetry
"""

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)


class TraceEventType(Enum):
    """追踪事件类型"""

    TASK_START = "task_start"
    TASK_END = "task_end"
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    SUBTASK_START = "subtask_start"
    SUBTASK_END = "subtask_end"
    MEMORY_RETRIEVAL = "memory_retrieval"
    LLM_CALL = "llm_call"


@dataclass
class TraceEvent:
    """追踪事件"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: TraceEventType = TraceEventType.THOUGHT
    timestamp: float = field(default_factory=time.time)
    task_id: str = ""
    parent_event_id: str | None = None
    step_number: int = 0

    # 事件内容
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # 性能指标
    duration_ms: float | None = None
    token_count: int | None = None
    cost_usd: float | None = None

    # 错误信息
    error: str | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["timestamp_iso"] = datetime.fromtimestamp(self.timestamp).isoformat()
        return data


class ExecutionTracer:
    """
    Agent 执行追踪器

    用法:
        tracer = ExecutionTracer()

        # 开始任务
        tracer.start_task("task_123", "What is 2 + 2?")

        # 记录思考
        tracer.record_thought("task_123", "I need to use calculator")

        # 记录行动
        tracer.record_action("task_123", "calculator", {"expression": "2 + 2"})

        # 记录观察
        tracer.record_observation("task_123", "4")

        # 结束任务
        tracer.end_task("task_123", final_result="The answer is 4")
    """

    def __init__(self, enable_otel: bool = True):
        """
        初始化追踪器

        Args:
            enable_otel: 是否启用 OpenTelemetry 追踪
        """
        self.enable_otel = enable_otel
        self.tracer = trace.get_tracer(__name__) if enable_otel else None

        # 内存存储（用于查询和分析）
        self.traces: dict[str, list[TraceEvent]] = {}
        self.active_spans: dict[str, Any] = {}
        self.task_metadata: dict[str, dict] = {}

        logger.info("ExecutionTracer initialized (OpenTelemetry: %s)", enable_otel)

    def start_task(
        self, task_id: str, task: str, mode: str = "react", metadata: dict | None = None
    ) -> TraceEvent:
        """
        开始追踪任务

        Args:
            task_id: 任务 ID
            task: 任务描述
            mode: 执行模式 (react/plan_execute/reflexion)
            metadata: 额外元数据

        Returns:
            追踪事件
        """
        event = TraceEvent(
            event_type=TraceEventType.TASK_START,
            task_id=task_id,
            content=task,
            metadata={"mode": mode, **(metadata or {})},
        )

        # 初始化任务追踪
        self.traces[task_id] = [event]
        self.task_metadata[task_id] = {
            "task": task,
            "mode": mode,
            "start_time": event.timestamp,
            "step_count": 0,
            "tool_calls": [],
            "llm_calls": 0,
        }

        # 创建 OpenTelemetry Span
        if self.enable_otel and self.tracer:
            span = self.tracer.start_span(
                f"agent.task.{mode}",
                attributes={
                    "task.id": task_id,
                    "task.description": task[:100],  # 限制长度
                    "task.mode": mode,
                },
            )
            self.active_spans[task_id] = span

        logger.info(f"[{task_id}] Task started: {task[:50]}...")
        return event

    def end_task(
        self, task_id: str, final_result: str, success: bool = True, error: str | None = None
    ) -> TraceEvent:
        """
        结束任务追踪

        Args:
            task_id: 任务 ID
            final_result: 最终结果
            success: 是否成功
            error: 错误信息

        Returns:
            追踪事件
        """
        if task_id not in self.traces:
            logger.warning(f"Task {task_id} not found in traces")
            return None

        # 计算执行时间
        start_event = self.traces[task_id][0]
        duration_ms = (time.time() - start_event.timestamp) * 1000

        event = TraceEvent(
            event_type=TraceEventType.TASK_END,
            task_id=task_id,
            content=final_result,
            duration_ms=duration_ms,
            error=error,
            metadata={
                "success": success,
                "step_count": self.task_metadata[task_id]["step_count"],
                "tool_calls": len(self.task_metadata[task_id]["tool_calls"]),
                "llm_calls": self.task_metadata[task_id]["llm_calls"],
            },
        )

        self.traces[task_id].append(event)

        # 结束 OpenTelemetry Span
        if self.enable_otel and task_id in self.active_spans:
            span = self.active_spans[task_id]
            span.set_attribute("task.success", success)
            span.set_attribute("task.duration_ms", duration_ms)
            span.set_attribute("task.step_count", self.task_metadata[task_id]["step_count"])

            if success:
                span.set_status(Status(StatusCode.OK))
            else:
                span.set_status(Status(StatusCode.ERROR, error or "Task failed"))

            span.end()
            del self.active_spans[task_id]

        logger.info(
            f"[{task_id}] Task ended: success={success}, "
            f"duration={duration_ms:.0f}ms, steps={self.task_metadata[task_id]['step_count']}"
        )

        return event

    def record_thought(
        self, task_id: str, thought: str, step_number: int | None = None
    ) -> TraceEvent:
        """
        记录思考过程

        Args:
            task_id: 任务 ID
            thought: 思考内容
            step_number: 步骤编号

        Returns:
            追踪事件
        """
        if step_number is None:
            self.task_metadata[task_id]["step_count"] += 1
            step_number = self.task_metadata[task_id]["step_count"]

        event = TraceEvent(
            event_type=TraceEventType.THOUGHT,
            task_id=task_id,
            step_number=step_number,
            content=thought,
        )

        self.traces[task_id].append(event)
        logger.debug(f"[{task_id}] Step {step_number} - Thought: {thought[:50]}...")

        return event

    def record_action(
        self,
        task_id: str,
        action: str,
        tool: str,
        params: dict[str, Any],
        step_number: int | None = None,
    ) -> TraceEvent:
        """
        记录行动决策

        Args:
            task_id: 任务 ID
            action: 行动描述
            tool: 工具名称
            params: 工具参数
            step_number: 步骤编号

        Returns:
            追踪事件
        """
        if step_number is None:
            step_number = self.task_metadata[task_id]["step_count"]

        event = TraceEvent(
            event_type=TraceEventType.ACTION,
            task_id=task_id,
            step_number=step_number,
            content=action,
            metadata={
                "tool": tool,
                "params": params,
            },
        )

        self.traces[task_id].append(event)
        self.task_metadata[task_id]["tool_calls"].append(tool)

        logger.debug(f"[{task_id}] Step {step_number} - Action: {tool} with {params}")

        return event

    def record_observation(
        self, task_id: str, result: Any, step_number: int | None = None
    ) -> TraceEvent:
        """
        记录观察结果

        Args:
            task_id: 任务 ID
            result: 工具执行结果
            step_number: 步骤编号

        Returns:
            追踪事件
        """
        if step_number is None:
            step_number = self.task_metadata[task_id]["step_count"]

        # 限制结果长度
        result_str = str(result)
        if len(result_str) > 500:
            result_str = result_str[:500] + "... (truncated)"

        event = TraceEvent(
            event_type=TraceEventType.OBSERVATION,
            task_id=task_id,
            step_number=step_number,
            content=result_str,
        )

        self.traces[task_id].append(event)
        logger.debug(f"[{task_id}] Step {step_number} - Observation: {result_str[:50]}...")

        return event

    def record_tool_call(
        self,
        task_id: str,
        tool_name: str,
        params: dict[str, Any],
        duration_ms: float,
        success: bool,
        result: Any = None,
        error: str | None = None,
    ) -> TraceEvent:
        """
        记录工具调用（包含性能指标）

        Args:
            task_id: 任务 ID
            tool_name: 工具名称
            params: 工具参数
            duration_ms: 执行时间（毫秒）
            success: 是否成功
            result: 执行结果
            error: 错误信息

        Returns:
            追踪事件
        """
        event = TraceEvent(
            event_type=TraceEventType.TOOL_CALL,
            task_id=task_id,
            content=tool_name,
            duration_ms=duration_ms,
            metadata={
                "tool_name": tool_name,
                "params": params,
                "success": success,
                "result": str(result)[:200] if result else None,
            },
            error=error,
        )

        self.traces[task_id].append(event)

        # OpenTelemetry Event
        if self.enable_otel and task_id in self.active_spans:
            span = self.active_spans[task_id]
            span.add_event(
                f"tool.{tool_name}",
                attributes={
                    "tool.name": tool_name,
                    "tool.duration_ms": duration_ms,
                    "tool.success": success,
                },
            )

        logger.info(
            f"[{task_id}] Tool call: {tool_name} - success={success}, duration={duration_ms:.0f}ms"
        )

        return event

    def record_llm_call(
        self,
        task_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: float,
        cost_usd: float,
    ) -> TraceEvent:
        """
        记录 LLM 调用（包含 Token 和成本）

        Args:
            task_id: 任务 ID
            model: 模型名称
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            duration_ms: 执行时间（毫秒）
            cost_usd: 成本（美元）

        Returns:
            追踪事件
        """
        total_tokens = prompt_tokens + completion_tokens

        event = TraceEvent(
            event_type=TraceEventType.LLM_CALL,
            task_id=task_id,
            content=model,
            duration_ms=duration_ms,
            token_count=total_tokens,
            cost_usd=cost_usd,
            metadata={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        )

        self.traces[task_id].append(event)
        self.task_metadata[task_id]["llm_calls"] += 1

        logger.debug(
            f"[{task_id}] LLM call: {model} - "
            f"tokens={total_tokens}, cost=${cost_usd:.4f}, duration={duration_ms:.0f}ms"
        )

        return event

    def get_trace(self, task_id: str) -> list[TraceEvent]:
        """获取任务的完整追踪记录"""
        return self.traces.get(task_id, [])

    def get_trace_summary(self, task_id: str) -> dict:
        """
        获取任务追踪摘要

        Returns:
            包含统计信息的字典
        """
        if task_id not in self.traces:
            return {}

        events = self.traces[task_id]
        metadata = self.task_metadata.get(task_id, {})

        # 计算统计信息
        total_duration = 0
        total_tokens = 0
        total_cost = 0.0
        tool_calls_count = 0
        llm_calls_count = 0

        for event in events:
            if event.duration_ms:
                total_duration += event.duration_ms
            if event.token_count:
                total_tokens += event.token_count
            if event.cost_usd:
                total_cost += event.cost_usd
            if event.event_type == TraceEventType.TOOL_CALL:
                tool_calls_count += 1
            if event.event_type == TraceEventType.LLM_CALL:
                llm_calls_count += 1

        return {
            "task_id": task_id,
            "task": metadata.get("task", ""),
            "mode": metadata.get("mode", ""),
            "step_count": metadata.get("step_count", 0),
            "event_count": len(events),
            "tool_calls_count": tool_calls_count,
            "llm_calls_count": llm_calls_count,
            "total_duration_ms": total_duration,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "start_time": metadata.get("start_time"),
        }

    def export_trace_json(self, task_id: str) -> str:
        """导出追踪记录为 JSON"""
        events = self.get_trace(task_id)
        return json.dumps([event.to_dict() for event in events], indent=2, ensure_ascii=False)

    def clear_trace(self, task_id: str):
        """清除任务的追踪记录（节省内存）"""
        if task_id in self.traces:
            del self.traces[task_id]
        if task_id in self.task_metadata:
            del self.task_metadata[task_id]
        if task_id in self.active_spans:
            del self.active_spans[task_id]


# 全局追踪器实例
_global_tracer: ExecutionTracer | None = None


def get_tracer() -> ExecutionTracer:
    """获取全局追踪器实例"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = ExecutionTracer()
    return _global_tracer


def set_tracer(tracer: ExecutionTracer):
    """设置全局追踪器实例"""
    global _global_tracer
    _global_tracer = tracer
