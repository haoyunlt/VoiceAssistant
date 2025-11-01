"""
Evaluation Metrics - 评测指标计算

提供各种评测指标的计算函数。
"""

from .evaluator import EvaluationResult


def compute_metrics(results: list[EvaluationResult]) -> dict:
    """
    计算评测指标

    Args:
        results: 评测结果列表

    Returns:
        指标字典
    """
    if not results:
        return {}

    # 基础统计
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful

    # 成功率
    success_rate = successful / total if total > 0 else 0.0

    # 平均步骤数（只计算成功的）
    steps = [r.step_count for r in results if r.success]
    avg_steps = sum(steps) / len(steps) if steps else 0.0

    # 平均执行时间
    times = [r.execution_time_ms for r in results if r.success]
    avg_execution_time_ms = sum(times) / len(times) if times else 0.0

    # 平均成本
    costs = [r.cost_usd for r in results if r.success and r.cost_usd]
    avg_cost_usd = sum(costs) / len(costs) if costs else 0.0

    # 平均工具调用次数
    tool_call_counts = [len(r.tool_calls) for r in results if r.success]
    avg_tool_calls = sum(tool_call_counts) / len(tool_call_counts) if tool_call_counts else 0.0

    # 答案正确性（LLM-as-Judge）
    correctness_scores = [r.answer_correctness for r in results if r.answer_correctness is not None]
    avg_answer_correctness = (
        sum(correctness_scores) / len(correctness_scores) if correctness_scores else None
    )

    # 工具选择准确率
    tool_accuracy_scores = [r.tool_accuracy for r in results if r.tool_accuracy is not None]
    avg_tool_accuracy = (
        sum(tool_accuracy_scores) / len(tool_accuracy_scores) if tool_accuracy_scores else None
    )

    # P95 延迟
    if times:
        sorted_times = sorted(times)
        p95_index = int(len(sorted_times) * 0.95)
        p95_latency_ms = sorted_times[p95_index]
    else:
        p95_latency_ms = 0.0

    return {
        "total_cases": total,
        "successful_cases": successful,
        "failed_cases": failed,
        "success_rate": success_rate,
        "avg_steps": avg_steps,
        "avg_execution_time_ms": avg_execution_time_ms,
        "p95_latency_ms": p95_latency_ms,
        "avg_cost_usd": avg_cost_usd,
        "avg_tool_calls": avg_tool_calls,
        "avg_answer_correctness": avg_answer_correctness,
        "avg_tool_accuracy": avg_tool_accuracy,
    }
