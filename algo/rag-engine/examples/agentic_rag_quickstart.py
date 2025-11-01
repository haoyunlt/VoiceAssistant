"""
Agentic RAG 快速开始示例

演示如何使用 ReAct Agent 处理复杂查询。

运行：
    python examples/agentic_rag_quickstart.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""

    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("请设置 OPENAI_API_KEY 环境变量")
        return

    logger.info("🚀 Agentic RAG 快速开始")

    # 1. 初始化 LLM 客户端
    from openai import AsyncOpenAI

    llm_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE"),
    )

    logger.info("✅ LLM 客户端初始化完成")

    # 2. 初始化工具
    from app.agent.tools.calculator import CalculatorTool
    from app.agent.tools.vector_search import VectorSearchTool
    from app.infrastructure.retrieval_client import RetrievalClient

    calculator = CalculatorTool()

    # 注意：这里需要启动检索服务，或使用模拟客户端
    retrieval_client = RetrievalClient(
        base_url=os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8005"),
        timeout=10.0,
    )
    vector_search = VectorSearchTool(retrieval_client)

    tools = [calculator, vector_search]
    logger.info(f"✅ 加载 {len(tools)} 个工具：{[t.name for t in tools]}")

    # 3. 创建 ReAct Agent
    from app.agent.react_agent import ReactAgent

    agent = ReactAgent(
        llm_client=llm_client,
        tools=tools,
        max_iterations=10,
        timeout_seconds=30,
    )

    logger.info("✅ ReAct Agent 初始化完成")

    # 4. 测试场景
    scenarios = [
        {
            "name": "计算题",
            "query": "如果一个产品原价 200 元，打 8 折后是多少钱？剩余库存 50 件，全部卖出能收入多少？",
            "expected_tools": ["calculator"],
        },
        {
            "name": "复合查询",
            "query": "什么是 RAG？如果我有 100 个文档，每个文档 1000 字，总共多少字？",
            "expected_tools": ["vector_search", "calculator"],
        },
    ]

    # 5. 执行测试
    for i, scenario in enumerate(scenarios, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"场景 {i}: {scenario['name']}")
        logger.info(f"{'=' * 80}")
        logger.info(f"查询: {scenario['query']}")

        try:
            result = await agent.solve(scenario["query"])

            if result.success:
                logger.info(f"✅ 成功 (迭代 {result.total_iterations} 次)")
                logger.info(f"答案: {result.answer}")

                # 显示推理步骤
                logger.info("\n推理步骤:")
                for step in result.steps:
                    logger.info(f"  步骤 {step.step_num}:")
                    logger.info(f"    思考: {step.thought.content[:100]}")
                    if step.action:
                        logger.info(f"    行动: {step.action.tool_name}")
                        logger.info(f"    参数: {step.action.params}")
                    logger.info(f"    观察: {step.observation[:100] if step.observation else '无'}")
            else:
                logger.error(f"❌ 失败: {result.error}")
                logger.error(f"答案: {result.answer}")

        except Exception as e:
            logger.error(f"❌ 异常: {e}", exc_info=True)

    logger.info(f"\n{'=' * 80}")
    logger.info("🎉 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
