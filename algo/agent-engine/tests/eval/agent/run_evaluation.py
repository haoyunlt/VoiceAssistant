#!/usr/bin/env python3
"""
运行 Agent 评测

用法:
    python run_evaluation.py --dataset benchmark.json --modes react plan_execute
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.agent_engine import AgentEngine
from tests.eval.agent.evaluator import AgentEvaluator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run Agent Evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/eval/agent/datasets/benchmark.json",
        help="Path to test dataset",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["react"],
        help="Execution modes to test (react, plan_execute, reflexion)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/eval/agent/reports/evaluation_result.json",
        help="Output report path",
    )
    parser.add_argument(
        "--enable-llm-judge",
        action="store_true",
        help="Enable LLM-as-Judge for answer correctness evaluation",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Starting Agent Evaluation")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Modes: {', '.join(args.modes)}")
    logger.info(f"Output: {args.output}")
    logger.info(f"LLM Judge: {'Enabled' if args.enable_llm_judge else 'Disabled'}")
    logger.info("=" * 60)

    # 初始化 Agent Engine
    logger.info("Initializing Agent Engine...")
    agent_engine = AgentEngine()
    await agent_engine.initialize()

    # 创建评测器
    evaluator = AgentEvaluator(agent_engine=agent_engine, enable_llm_judge=args.enable_llm_judge)

    # 加载测试用例
    logger.info(f"Loading test cases from {args.dataset}...")
    test_cases = evaluator.load_test_cases(args.dataset)

    if not test_cases:
        logger.error("No test cases loaded. Exiting.")
        return

    # 运行评测
    logger.info("Running evaluation...")
    results = await evaluator.evaluate(test_cases=test_cases, modes=args.modes, save_traces=True)

    # 生成报告
    logger.info("Generating report...")
    report = evaluator.generate_report(results)

    # 保存报告
    evaluator.save_report(report, args.output)

    # 打印摘要
    evaluator.print_summary(report)

    # 清理
    await agent_engine.cleanup()

    logger.info("\nEvaluation completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
