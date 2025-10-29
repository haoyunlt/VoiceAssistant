"""
Agent Evaluator - Agent 评测器

功能:
- 运行测试用例并记录执行轨迹
- 计算多维度评测指标
- 生成评测报告
- 支持 LLM-as-Judge 评估
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """测试用例"""

    id: str
    category: str  # simple_calculation, knowledge_retrieval, multi_step_reasoning, tool_composition
    task: str
    expected_answer: str | None = None
    expected_tools: list[str] | None = None
    max_steps: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """评测结果"""

    test_case_id: str
    task: str
    mode: str

    # 执行结果
    success: bool
    final_answer: str
    execution_time_ms: float
    step_count: int
    tool_calls: list[str]

    # 评测指标
    answer_correctness: float | None = None  # 0-1, LLM-as-Judge 评分
    tool_accuracy: float | None = None  # 工具选择准确率
    cost_usd: float | None = None

    # 错误信息
    error: str | None = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


class AgentEvaluator:
    """
    Agent 评测器

    用法:
        evaluator = AgentEvaluator(agent_engine)

        # 加载测试用例
        test_cases = evaluator.load_test_cases("tests/eval/agent/datasets/benchmark.json")

        # 运行评测
        results = await evaluator.evaluate(
            test_cases=test_cases,
            modes=["react", "plan_execute"]
        )

        # 生成报告
        report = evaluator.generate_report(results)
        evaluator.save_report(report, "reports/evaluation_result.json")
    """

    def __init__(
        self,
        agent_engine: Any,  # AgentEngine 实例
        llm_judge_model: str = "gpt-4",
        enable_llm_judge: bool = True,
    ):
        """
        初始化评测器

        Args:
            agent_engine: Agent Engine 实例
            llm_judge_model: LLM-as-Judge 使用的模型
            enable_llm_judge: 是否启用 LLM-as-Judge
        """
        self.agent_engine = agent_engine
        self.llm_judge_model = llm_judge_model
        self.enable_llm_judge = enable_llm_judge

        logger.info(
            f"AgentEvaluator initialized (LLM Judge: {llm_judge_model if enable_llm_judge else 'disabled'})"
        )

    def load_test_cases(self, dataset_path: str) -> list[TestCase]:
        """
        加载测试用例

        Args:
            dataset_path: 数据集文件路径（JSON）

        Returns:
            测试用例列表
        """
        path = Path(dataset_path)
        if not path.exists():
            logger.error(f"Dataset file not found: {dataset_path}")
            return []

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        test_cases = []
        for item in data:
            test_cases.append(TestCase(**item))

        logger.info(f"Loaded {len(test_cases)} test cases from {dataset_path}")
        return test_cases

    async def evaluate(
        self, test_cases: list[TestCase], modes: list[str] = None, save_traces: bool = True
    ) -> list[EvaluationResult]:
        """
        运行评测

        Args:
            test_cases: 测试用例列表
            modes: 执行模式列表（默认: ["react"]）
            save_traces: 是否保存执行轨迹

        Returns:
            评测结果列表
        """
        if modes is None:
            modes = ["react"]

        results = []
        total = len(test_cases) * len(modes)
        completed = 0

        logger.info(
            f"Starting evaluation: {len(test_cases)} cases × {len(modes)} modes = {total} runs"
        )

        for mode in modes:
            for test_case in test_cases:
                completed += 1
                logger.info(f"[{completed}/{total}] Running {test_case.id} with {mode}")

                try:
                    result = await self._evaluate_single(test_case, mode, save_traces)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error evaluating {test_case.id}: {e}", exc_info=True)

                    # 创建失败结果
                    results.append(
                        EvaluationResult(
                            test_case_id=test_case.id,
                            task=test_case.task,
                            mode=mode,
                            success=False,
                            final_answer="",
                            execution_time_ms=0,
                            step_count=0,
                            tool_calls=[],
                            error=str(e),
                        )
                    )

        logger.info(f"Evaluation completed: {len(results)} results")
        return results

    async def _evaluate_single(
        self, test_case: TestCase, mode: str, save_traces: bool
    ) -> EvaluationResult:
        """评测单个用例"""
        start_time = time.time()

        # 执行任务
        try:
            result = await self.agent_engine.execute(
                task=test_case.task,
                mode=mode,
                max_steps=test_case.max_steps,
            )

            success = True
            final_answer = result.get("final_answer", "")
            step_count = result.get("step_count", 0)
            tool_calls = result.get("tool_calls", [])
            error = None

        except Exception as e:
            success = False
            final_answer = ""
            step_count = 0
            tool_calls = []
            error = str(e)

        execution_time_ms = (time.time() - start_time) * 1000

        # 计算工具选择准确率
        tool_accuracy = None
        if test_case.expected_tools:
            tool_accuracy = self._compute_tool_accuracy(tool_calls, test_case.expected_tools)

        # LLM-as-Judge 评估答案正确性
        answer_correctness = None
        if self.enable_llm_judge and test_case.expected_answer and success:
            answer_correctness = await self._judge_answer_correctness(
                task=test_case.task,
                expected_answer=test_case.expected_answer,
                actual_answer=final_answer,
            )

        # 估算成本（简化版，实际应从追踪器获取）
        cost_usd = result.get("cost_usd", 0.0)

        return EvaluationResult(
            test_case_id=test_case.id,
            task=test_case.task,
            mode=mode,
            success=success,
            final_answer=final_answer,
            execution_time_ms=execution_time_ms,
            step_count=step_count,
            tool_calls=tool_calls,
            answer_correctness=answer_correctness,
            tool_accuracy=tool_accuracy,
            cost_usd=cost_usd,
            error=error,
        )

    def _compute_tool_accuracy(self, actual_tools: list[str], expected_tools: list[str]) -> float:
        """
        计算工具选择准确率

        使用 Jaccard 相似度: |intersection| / |union|
        """
        if not expected_tools:
            return 1.0 if not actual_tools else 0.0

        actual_set = set(actual_tools)
        expected_set = set(expected_tools)

        intersection = actual_set & expected_set
        union = actual_set | expected_set

        if not union:
            return 1.0

        return len(intersection) / len(union)

    async def _judge_answer_correctness(
        self, task: str, expected_answer: str, actual_answer: str
    ) -> float:
        """
        LLM-as-Judge: 评估答案正确性

        Returns:
            0-1 的评分
        """
        try:
            # 构建评估 Prompt
            prompt = f"""你是一个严格的答案评估专家。请评估以下答案的正确性。

任务: {task}

参考答案: {expected_answer}

实际答案: {actual_answer}

请根据以下标准评分（0-1）:
- 1.0: 完全正确，内容准确且完整
- 0.8: 基本正确，有微小瑕疵
- 0.6: 部分正确，缺少关键信息
- 0.4: 有相关内容，但不够准确
- 0.2: 答非所问
- 0.0: 完全错误

只输出一个 0-1 之间的数字，不要解释。"""

            # 调用 LLM（这里需要实际的 LLM 客户端）
            # 简化实现：使用 agent_engine 的 llm_client
            if hasattr(self.agent_engine, "llm_client"):
                response = await self.agent_engine.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.llm_judge_model,
                    temperature=0.0,
                )

                # 解析评分
                score_str = response.strip()
                score = float(score_str)
                return max(0.0, min(1.0, score))  # 限制在 [0, 1]

            # 降级：简单的字符串匹配
            if expected_answer.lower() in actual_answer.lower():
                return 0.8
            return 0.0

        except Exception as e:
            logger.error(f"Error in LLM-as-Judge: {e}")
            return 0.0

    def generate_report(self, results: list[EvaluationResult]) -> dict:
        """
        生成评测报告

        Args:
            results: 评测结果列表

        Returns:
            报告字典
        """
        from .metrics import compute_metrics

        # 计算整体指标
        overall_metrics = compute_metrics(results)

        # 按模式分组统计
        mode_metrics = {}
        for mode in {r.mode for r in results}:
            mode_results = [r for r in results if r.mode == mode]
            mode_metrics[mode] = compute_metrics(mode_results)

        # 按类别分组统计
        category_metrics = {}
        test_cases_by_category = {}
        for result in results:
            # 从 test_case_id 提取类别（假设格式为 "category_xxx"）
            category = result.test_case_id.split("_")[0]
            if category not in category_metrics:
                category_metrics[category] = []
                test_cases_by_category[category] = []

            category_metrics[category].append(result)
            test_cases_by_category[category].append(result.test_case_id)

        for category in category_metrics:
            category_metrics[category] = compute_metrics(category_metrics[category])

        # 生成报告
        report = {
            "summary": {
                "total_cases": len(results),
                "timestamp": time.time(),
                "modes": list(mode_metrics.keys()),
            },
            "overall_metrics": overall_metrics,
            "mode_metrics": mode_metrics,
            "category_metrics": category_metrics,
            "detailed_results": [r.to_dict() for r in results],
        }

        logger.info(
            f"Generated evaluation report: success_rate={overall_metrics['success_rate']:.2%}"
        )

        return report

    def save_report(self, report: dict, output_path: str):
        """
        保存评测报告

        Args:
            report: 报告字典
            output_path: 输出文件路径
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Evaluation report saved to {output_path}")

    def print_summary(self, report: dict):
        """打印评测摘要"""
        metrics = report["overall_metrics"]

        print("\n" + "=" * 60)
        print("📊 Agent Evaluation Report")
        print("=" * 60)
        print(f"Total Test Cases: {report['summary']['total_cases']}")
        print(f"Modes: {', '.join(report['summary']['modes'])}")
        print("\n--- Overall Metrics ---")
        print(f"Success Rate:           {metrics['success_rate']:.2%}")
        print(f"Avg Steps:              {metrics['avg_steps']:.1f}")
        print(f"Avg Execution Time:     {metrics['avg_execution_time_ms']:.0f} ms")
        print(f"Avg Cost:               ${metrics['avg_cost_usd']:.4f}")

        if metrics.get("avg_answer_correctness") is not None:
            print(f"Avg Answer Correctness: {metrics['avg_answer_correctness']:.2f}")
        if metrics.get("avg_tool_accuracy") is not None:
            print(f"Avg Tool Accuracy:      {metrics['avg_tool_accuracy']:.2%}")

        print("\n--- Mode Comparison ---")
        for mode, mode_metrics in report["mode_metrics"].items():
            print(f"\n{mode}:")
            print(f"  Success Rate: {mode_metrics['success_rate']:.2%}")
            print(f"  Avg Steps:    {mode_metrics['avg_steps']:.1f}")
            print(f"  Avg Time:     {mode_metrics['avg_execution_time_ms']:.0f} ms")

        print("\n" + "=" * 60)
