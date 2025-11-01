"""
Multi-Agent + LangGraph Integration Example
展示完整的集成使用方式
"""

import asyncio
import logging

from app.core.langgraph_engine import CheckpointManager, LangGraphWorkflowEngine
from app.core.multi_agent.coordinator import Agent, AgentRole
from app.core.multi_agent.enhanced_conflict_resolver import ConflictType

# 假设导入（实际使用时需要正确的导入路径）
from app.core.multi_agent.enhanced_coordinator import EnhancedMultiAgentCoordinator
from app.core.multi_agent.task_scheduler import TaskPriority
from app.core.workflow_visualizer import visualize_execution, visualize_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_multi_agent_collaboration():
    """示例：Multi-Agent协作"""
    print("\n=== Multi-Agent 协作示例 ===\n")

    # 模拟LLM和工具
    class MockLLMClient:
        async def generate(self, prompt, **kwargs):
            return f"模拟回答: {prompt[:50]}..."

    class MockToolRegistry:
        async def execute_tool(self, name, **kwargs):
            return f"工具 {name} 执行成功"

    llm_client = MockLLMClient()
    tool_registry = MockToolRegistry()

    # 1. 创建增强协调器
    coordinator = EnhancedMultiAgentCoordinator(llm_client, tool_registry)

    # 2. 注册Agents
    print("📝 注册Agents...")

    researcher = Agent("researcher_01", AgentRole.RESEARCHER, llm_client)
    await coordinator.register_agent_with_capabilities(
        agent=researcher,
        capabilities={"research": 0.9, "analysis": 0.8, "data_collection": 0.85},
        success_rate=0.95,
        avg_response_time=2.5,
    )

    planner = Agent("planner_01", AgentRole.PLANNER, llm_client)
    await coordinator.register_agent_with_capabilities(
        agent=planner,
        capabilities={"planning": 0.85, "strategy": 0.9, "roadmap": 0.8},
        success_rate=0.90,
        avg_response_time=3.0,
    )

    executor = Agent("executor_01", AgentRole.EXECUTOR, llm_client)
    await coordinator.register_agent_with_capabilities(
        agent=executor,
        capabilities={"execution": 0.88, "implementation": 0.85},
        success_rate=0.92,
        avg_response_time=2.8,
    )

    print(f"✅ 已注册 {len(coordinator.agents)} 个Agents\n")

    # 3. 执行协作任务
    print("🚀 执行协作任务...")

    result = await coordinator.collaborate_with_scheduling(
        task_description="分析Q4市场趋势并制定增长策略",
        priority=TaskPriority.HIGH,
        required_capabilities=["research", "planning"],
        timeout=30,
    )

    print(f"\n任务结果:")
    print(f"  成功: {result['success']}")
    print(f"  分配Agent: {result.get('agent', 'N/A')}")
    print(f"  执行时间: {result.get('execution_time', 0):.2f}s")
    print(f"  调度质量: {result.get('schedule_quality', 0):.2f}")

    # 4. 获取统计信息
    print("\n📊 系统统计:")
    comm_stats = coordinator.get_communication_stats()
    print(f"  消息总数: {comm_stats['total_messages']}")
    print(f"  平均延迟: {comm_stats['avg_latency']:.3f}s")
    print(f"  失败率: {comm_stats['failure_rate']:.1%}")

    # 5. 健康检查
    print("\n🏥 健康检查:")
    health = await coordinator.health_check()
    print(f"  系统健康: {'✅' if health['healthy'] else '❌'}")
    print(f"  通信异常: {len(health['anomalies'])} 个")
    if health["anomalies"]:
        for anomaly in health["anomalies"]:
            print(f"    - {anomaly['type']}: {anomaly['description']}")

    # 6. 能力画像
    print("\n🎯 Agent能力画像:")
    for agent_id in coordinator.agents.keys():
        profile = coordinator.get_agent_capabilities(agent_id)
        if profile:
            print(f"  {agent_id}:")
            print(f"    能力: {list(profile['capabilities'].keys())}")
            print(f"    成功率: {profile['success_rate']:.2%}")
            print(f"    平均响应: {profile['avg_response_time']:.2f}s")


async def example_langgraph_workflow():
    """示例：LangGraph工作流"""
    print("\n=== LangGraph 工作流示例 ===\n")

    # 1. 初始化引擎
    checkpoint_manager = CheckpointManager()  # 本地存储
    engine = LangGraphWorkflowEngine(checkpoint_manager)

    # 2. 定义工作流函数
    async def analyze_task(context):
        logger.info("分析任务...")
        return {"analysis": "任务分析完成", "complexity": "high"}

    async def retrieve_documents(context):
        logger.info("检索文档...")
        return {"documents": ["doc1.pdf", "doc2.pdf", "doc3.pdf"]}

    async def needs_review(context):
        # 决策：文档数量超过2个需要审查
        doc_count = len(context.get("documents", []))
        logger.info(f"决策: 文档数={doc_count}, 需要审查={doc_count > 2}")
        return doc_count > 2

    async def review_result(context):
        logger.info("审查结果...")
        return {"review": "审查通过", "quality_score": 0.92}

    async def finalize(context):
        logger.info("完成工作流...")
        return {"status": "completed", "final_report": "工作流执行成功"}

    # 3. 注册函数
    engine.register_function("analyze_task", analyze_task)
    engine.register_function("retrieve_documents", retrieve_documents)
    engine.register_function("needs_review", needs_review)
    engine.register_function("review_result", review_result)
    engine.register_function("finalize", finalize)

    # 4. 创建工作流配置
    workflow_config = {
        "nodes": [
            {"id": "start", "type": "action", "function": "analyze_task", "label": "分析任务"},
            {
                "id": "retrieve",
                "type": "action",
                "function": "retrieve_documents",
                "label": "检索文档",
            },
            {"id": "decide", "type": "decision", "condition": "needs_review", "label": "需要审查?"},
            {"id": "review", "type": "action", "function": "review_result", "label": "审查结果"},
            {"id": "end", "type": "action", "function": "finalize", "label": "完成"},
        ],
        "edges": [
            {"from": "start", "to": "retrieve"},
            {"from": "retrieve", "to": "decide"},
            {"from": "decide", "to": {"review": "needs_review", "end": "else"}},
            {"from": "review", "to": "end"},
        ],
        "entry": "start",
    }

    print("📝 创建工作流...")
    workflow_id = engine.create_workflow(workflow_config)
    print(f"✅ 工作流ID: {workflow_id}\n")

    # 5. 可视化工作流
    print("🎨 工作流结构 (Mermaid):")
    mermaid = visualize_workflow(workflow_config)
    print(mermaid)
    print()

    # 6. 执行工作流
    print("🚀 执行工作流...\n")
    result = await engine.execute(
        workflow_id,
        initial_data={"task": "分析客户数据", "user_id": "user_123"},
        entry_node="start",
        save_checkpoints=True,
    )

    print(f"\n执行结果:")
    print(f"  状态: {result['status']}")
    print(f"  执行路径: {' → '.join(result['node_history'])}")
    print(f"  最终数据: {result['variables'].get('final_report', 'N/A')}")

    # 7. 可视化执行追踪
    print("\n🎨 执行追踪 (Mermaid):")
    trace_mermaid = visualize_execution(workflow_config, node_history=result["node_history"])
    print(trace_mermaid)
    print()

    # 8. 统计信息
    stats = engine.get_stats()
    print(f"📊 引擎统计:")
    print(f"  总执行次数: {stats['total_executions']}")
    print(f"  成功次数: {stats['successful_executions']}")
    print(f"  成功率: {stats['success_rate']:.1%}")


async def example_workflow_recovery():
    """示例：工作流恢复"""
    print("\n=== 工作流恢复示例 ===\n")

    checkpoint_manager = CheckpointManager()
    engine = LangGraphWorkflowEngine(checkpoint_manager)

    # 定义会失败的函数
    call_count = 0

    async def step1(context):
        logger.info("步骤1: 初始化")
        return {"step1": "completed"}

    async def step2(context):
        logger.info("步骤2: 处理")
        return {"step2": "completed"}

    async def step3_with_failure(context):
        nonlocal call_count
        call_count += 1
        logger.info(f"步骤3: 尝试执行 (第{call_count}次)")

        if call_count == 1:
            # 第一次执行失败
            raise Exception("模拟失败：网络超时")
        else:
            # 第二次执行成功
            logger.info("步骤3: 执行成功")
            return {"step3": "completed"}

    async def step4(context):
        logger.info("步骤4: 完成")
        return {"final": "all_done"}

    # 注册函数
    engine.register_function("step1", step1)
    engine.register_function("step2", step2)
    engine.register_function("step3", step3_with_failure)
    engine.register_function("step4", step4)

    # 创建工作流
    workflow_config = {
        "nodes": [
            {"id": "s1", "type": "action", "function": "step1"},
            {"id": "s2", "type": "action", "function": "step2"},
            {"id": "s3", "type": "action", "function": "step3"},
            {"id": "s4", "type": "action", "function": "step4"},
        ],
        "edges": [
            {"from": "s1", "to": "s2"},
            {"from": "s2", "to": "s3"},
            {"from": "s3", "to": "s4"},
        ],
        "entry": "s1",
    }

    workflow_id = engine.create_workflow(workflow_config)

    # 第一次执行（会失败）
    print("🚀 第一次执行 (会在步骤3失败)...")
    try:
        await engine.execute(workflow_id, initial_data={"task": "测试恢复"})
    except Exception as e:
        print(f"❌ 执行失败: {e}\n")

    # 查看checkpoint
    status = engine.get_workflow_status(workflow_id)
    print(f"📌 Checkpoint状态:")
    print(f"  当前节点: {status['current_node']}")
    print(f"  已执行: {status['node_history']}")
    print(f"  状态: {status['status']}")
    print()

    # 恢复执行
    print("🔄 恢复执行...")
    result = await engine.resume(workflow_id)

    print(f"\n恢复结果:")
    print(f"  状态: {result['status']}")
    print(f"  完整路径: {' → '.join(result['node_history'])}")
    print(f"  最终数据: {result['variables']}")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Multi-Agent + LangGraph 集成示例")
    print("=" * 60)

    # 1. Multi-Agent协作
    await example_multi_agent_collaboration()

    print("\n" + "-" * 60 + "\n")

    # 2. LangGraph工作流
    await example_langgraph_workflow()

    print("\n" + "-" * 60 + "\n")

    # 3. 工作流恢复
    await example_workflow_recovery()

    print("\n" + "=" * 60)
    print("  ✅ 所有示例执行完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
