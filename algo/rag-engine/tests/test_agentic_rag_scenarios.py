"""
Agentic RAG 复杂场景测试

测试 3 个复杂场景：
1. 计算类问题
2. 实时信息查询
3. 多步骤推理
"""

import os

import pytest

# 跳过所有测试，除非设置了环境变量
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="需要 OPENAI_API_KEY 环境变量"
)


@pytest.fixture
async def agent_service():
    """初始化 Agentic RAG 服务"""
    from app.infrastructure.retrieval_client import RetrievalClient
    from app.services.ultimate_rag_service import UltimateRAGService
    from openai import AsyncOpenAI

    llm_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_API_BASE")
    )

    retrieval_client = RetrievalClient(
        base_url=os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8005"), timeout=10.0
    )

    # 初始化服务（仅启用 Agent）
    service = UltimateRAGService(
        retrieval_client=retrieval_client,
        llm_client=llm_client,
        enable_hybrid=False,
        enable_rerank=False,
        enable_cache=False,
        enable_graph=False,
        enable_decomposition=False,
        enable_self_rag=False,
        enable_compression=False,
        enable_agent=True,
        agent_max_iterations=10,
    )

    yield service


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgenticRAGScenarios:
    """Agentic RAG 复杂场景测试"""

    async def test_scenario_1_calculation(self, agent_service):
        """
        场景 1: 计算类问题

        问题: 如果公司 2023 年营收 100M，2024 年营收 130M，增长率是多少？
        预期: 使用 calculator 工具，返回 30%
        """
        query = "如果公司 2023 年营收 100M，2024 年营收 130M，增长率是多少？"

        result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

        # 验证结果
        assert result["strategy"] == "agentic_rag"
        assert "agent_info" in result
        assert result["agent_info"]["success"]
        assert result["agent_info"]["iterations"] <= 5

        # 验证使用了计算器工具
        tools_used = result["agent_info"]["tools_used"]
        assert "calculator" in tools_used

        # 验证答案包含 30% 或类似表达
        answer = result["answer"].lower()
        assert any(keyword in answer for keyword in ["30", "三十", "percent", "%"])

        print("\n✅ 场景 1 通过")
        print(f"答案: {result['answer']}")
        print(f"迭代次数: {result['agent_info']['iterations']}")
        print(f"使用的工具: {tools_used}")

    async def test_scenario_2_realtime_info(self, agent_service):
        """
        场景 2: 实时信息查询

        问题: 今天北京的天气如何？
        预期: 使用 web_search 工具，返回实时天气
        """
        query = "今天北京的天气如何？"

        result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

        # 验证结果
        assert result["strategy"] == "agentic_rag"
        assert result["agent_info"]["success"]

        # 验证使用了网络搜索工具
        tools_used = result["agent_info"]["tools_used"]
        assert "web_search" in tools_used

        # 验证答案提到了北京或天气
        answer = result["answer"].lower()
        assert "北京" in answer or "beijing" in answer

        print("\n✅ 场景 2 通过")
        print(f"答案: {result['answer'][:200]}...")
        print(f"迭代次数: {result['agent_info']['iterations']}")
        print(f"使用的工具: {tools_used}")

    async def test_scenario_3_multi_step_reasoning(self, agent_service):
        """
        场景 3: 多步骤推理

        问题: 找到销量最高的产品，并计算其与平均销量的差距
        预期: 先用 sql_query 查询，再用 calculator 计算
        """
        query = "找到销量最高的产品，并计算其与平均销量的差距"

        result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

        # 验证结果
        assert result["strategy"] == "agentic_rag"
        assert result["agent_info"]["success"]
        assert result["agent_info"]["iterations"] >= 2  # 至少2步

        # 验证使用了多个工具
        tools_used = result["agent_info"]["tools_used"]
        # 可能使用 sql_query + calculator，或 vector_search + calculator
        assert len(tools_used) >= 2

        print("\n✅ 场景 3 通过")
        print(f"答案: {result['answer']}")
        print(f"迭代次数: {result['agent_info']['iterations']}")
        print(f"使用的工具: {tools_used}")

    async def test_scenario_4_complex_mixed(self, agent_service):
        """
        场景 4: 复杂混合查询

        问题: 什么是 RAG？如果我有 100 个文档，每个 1000 字，总共多少字？
        预期: 先用 vector_search 检索，再用 calculator 计算
        """
        query = "什么是 RAG？如果我有 100 个文档，每个 1000 字，总共多少字？"

        result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

        # 验证结果
        assert result["strategy"] == "agentic_rag"
        assert result["agent_info"]["success"]

        # 验证使用了多个工具
        tools_used = result["agent_info"]["tools_used"]
        # 应该包含 vector_search（查询RAG）和 calculator（计算总字数）
        assert len(tools_used) >= 2

        # 验证答案包含 RAG 的解释和计算结果
        answer = result["answer"].lower()
        assert "rag" in answer or "检索" in answer
        assert "100000" in answer or "十万" in answer  # 100 * 1000 = 100000

        print("\n✅ 场景 4 通过")
        print(f"答案: {result['answer'][:300]}...")
        print(f"迭代次数: {result['agent_info']['iterations']}")
        print(f"使用的工具: {tools_used}")

    async def test_scenario_5_fallback_to_standard_rag(self, agent_service):
        """
        场景 5: Agent 失败后降级到标准 RAG

        问题: 一个简单的问答（不需要 Agent）
        预期: 自动路由到标准 RAG，或 Agent 快速收敛
        """
        query = "什么是机器学习？"

        result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

        # 验证结果存在
        assert "answer" in result
        assert len(result["answer"]) > 0

        # 可能是 Agent 处理，也可能降级到标准 RAG
        strategy = result.get("strategy")
        assert strategy in ["agentic_rag", "hybrid_retrieval", "base"]

        print("\n✅ 场景 5 通过")
        print(f"策略: {strategy}")
        print(f"答案: {result['answer'][:200]}...")


@pytest.mark.asyncio
@pytest.mark.performance
class TestAgenticRAGPerformance:
    """Agentic RAG 性能测试"""

    async def test_convergence_rate(self, agent_service):
        """测试收敛率"""
        queries = [
            "2 + 3 等于多少？",
            "100 乘以 5 等于多少？",
            "如果增长 20%，原值 100，新值是多少？",
        ]

        success_count = 0
        total_iterations = 0

        for query in queries:
            result = await agent_service.query(query=query, tenant_id="test", use_agent=True)

            if result.get("agent_info", {}).get("success"):
                success_count += 1

            total_iterations += result.get("agent_info", {}).get("iterations", 0)

        # 验证收敛率 >95%
        convergence_rate = success_count / len(queries)
        assert convergence_rate >= 0.95

        # 验证平均迭代次数 <5
        avg_iterations = total_iterations / len(queries)
        assert avg_iterations < 5

        print("\n✅ 性能测试通过")
        print(f"收敛率: {convergence_rate:.2%}")
        print(f"平均迭代次数: {avg_iterations:.2f}")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])
