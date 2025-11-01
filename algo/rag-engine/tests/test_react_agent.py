"""
ReAct Agent 测试用例

演示 Agentic RAG 的基本功能。
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agent.react_agent import ReactAgent, Action, Thought, ThoughtType
from app.agent.tools.calculator import CalculatorTool
from app.agent.tools.vector_search import VectorSearchTool


@pytest.fixture
def mock_llm_client():
    """模拟 LLM 客户端"""
    client = MagicMock()
    return client


@pytest.fixture
def mock_retrieval_client():
    """模拟检索客户端"""
    client = AsyncMock()
    client.search = AsyncMock(
        return_value={
            "documents": [
                {"content": "RAG 是检索增强生成技术", "score": 0.95},
                {"content": "RAG 结合了检索和生成", "score": 0.88},
            ]
        }
    )
    return client


@pytest.fixture
def calculator_tool():
    """计算器工具"""
    return CalculatorTool()


@pytest.fixture
def vector_search_tool(mock_retrieval_client):
    """向量检索工具"""
    return VectorSearchTool(mock_retrieval_client)


class TestCalculatorTool:
    """测试计算器工具"""

    @pytest.mark.asyncio
    async def test_simple_calculation(self, calculator_tool):
        """测试简单计算"""
        result = await calculator_tool.execute({"expression": "2 + 3"})

        assert result["result"] == 5.0
        assert "5.00" in result["text"]

    @pytest.mark.asyncio
    async def test_percentage_calculation(self, calculator_tool):
        """测试百分比计算"""
        # 增长率计算：(130 - 100) / 100 * 100
        result = await calculator_tool.execute({"expression": "(130 - 100) / 100 * 100"})

        assert result["result"] == 30.0
        assert "30" in result["text"]

    @pytest.mark.asyncio
    async def test_complex_calculation(self, calculator_tool):
        """测试复杂计算"""
        result = await calculator_tool.execute({"expression": "(100 * 1.3 - 100) / 100"})

        assert abs(result["result"] - 0.3) < 0.01

    @pytest.mark.asyncio
    async def test_invalid_expression(self, calculator_tool):
        """测试非法表达式"""
        result = await calculator_tool.execute({"expression": "import os"})

        assert result["result"] is None
        assert "error" in result


class TestVectorSearchTool:
    """测试向量检索工具"""

    @pytest.mark.asyncio
    async def test_search_success(self, vector_search_tool):
        """测试检索成功"""
        result = await vector_search_tool.execute({"query": "什么是RAG？"})

        assert result["count"] == 2
        assert len(result["documents"]) == 2
        assert "找到 2 个相关文档" in result["text"]

    @pytest.mark.asyncio
    async def test_search_with_top_k(self, vector_search_tool):
        """测试指定 top_k"""
        result = await vector_search_tool.execute({"query": "什么是RAG？", "top_k": 3})

        # 模拟返回固定结果
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_search_empty_query(self, vector_search_tool):
        """测试空查询"""
        with pytest.raises(ValueError, match="query 参数不能为空"):
            await vector_search_tool.execute({"query": ""})


class TestReactAgent:
    """测试 ReAct Agent"""

    def create_agent_with_mocked_llm(self, llm_responses, tools):
        """创建带模拟 LLM 的 Agent"""
        mock_llm = MagicMock()

        # 模拟多轮对话
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            response = llm_responses[call_count] if call_count < len(llm_responses) else llm_responses[-1]
            call_count += 1

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = response
            return mock_response

        mock_llm.chat.completions.create = mock_create

        return ReactAgent(llm_client=mock_llm, tools=tools, max_iterations=5)

    @pytest.mark.asyncio
    async def test_agent_simple_calculation(self, calculator_tool):
        """测试 Agent 执行简单计算"""
        llm_responses = [
            # 第一轮：决定使用计算器
            """思考: 这是一个数学计算问题，需要使用计算器工具
行动: calculator
参数: {"expression": "(130 - 100) / 100 * 100"}""",
            # 第二轮：给出最终答案
            """思考: 计算器返回了结果 30.0，即增长率为 30%
最终答案: 增长率为 30%。""",
        ]

        agent = self.create_agent_with_mocked_llm(llm_responses, [calculator_tool])

        result = await agent.solve("如果 2023 年营收 100M，2024 年营收 130M，增长率是多少？")

        assert result.success
        assert "30%" in result.answer
        assert result.total_iterations == 2

    @pytest.mark.asyncio
    async def test_agent_with_retrieval_and_calculation(self, vector_search_tool, calculator_tool):
        """测试 Agent 结合检索和计算"""
        llm_responses = [
            # 第一轮：先检索
            """思考: 需要先查找相关数据
行动: vector_search
参数: {"query": "公司营收数据", "top_k": 5}""",
            # 第二轮：计算
            """思考: 从检索结果中提取到 2023 年营收 100M，2024 年营收 130M，现在计算增长率
行动: calculator
参数: {"expression": "(130 - 100) / 100 * 100"}""",
            # 第三轮：最终答案
            """思考: 增长率为 30%
最终答案: 根据检索到的数据，公司 2024 年相比 2023 年增长率为 30%。""",
        ]

        agent = self.create_agent_with_mocked_llm(
            llm_responses, [vector_search_tool, calculator_tool]
        )

        result = await agent.solve("公司去年相比前年的增长率是多少？")

        assert result.success
        assert result.total_iterations == 3
        assert len(result.steps) == 3

    @pytest.mark.asyncio
    async def test_agent_max_iterations(self, calculator_tool):
        """测试 Agent 最大迭代次数"""
        # 模拟一直不收敛
        llm_responses = [
            """思考: 继续思考
行动: calculator
参数: {"expression": "1 + 1"}"""
        ] * 10

        agent = self.create_agent_with_mocked_llm(llm_responses, [calculator_tool])
        agent.max_iterations = 3

        result = await agent.solve("测试问题")

        assert not result.success
        assert result.error == "max_iterations_reached"
        assert result.total_iterations == 3

    @pytest.mark.asyncio
    async def test_agent_timeout(self, calculator_tool):
        """测试 Agent 超时"""

        async def slow_execute(params):
            await asyncio.sleep(2)  # 模拟慢速工具
            return {"text": "结果", "result": 1}

        calculator_tool.execute = slow_execute

        llm_responses = [
            """思考: 执行计算
行动: calculator
参数: {"expression": "1 + 1"}"""
        ]

        agent = self.create_agent_with_mocked_llm(llm_responses, [calculator_tool])
        agent.timeout_seconds = 1  # 1秒超时

        result = await agent.solve("测试问题")

        assert not result.success
        assert result.error == "timeout"


# ==================== 集成测试 ====================


class TestAgenticRAGIntegration:
    """Agentic RAG 集成测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_calculation_scenario(self):
        """测试真实计算场景（需要真实 LLM）"""
        # 跳过，除非设置了环境变量
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("需要 OPENAI_API_KEY 环境变量")

        from openai import AsyncOpenAI

        llm_client = AsyncOpenAI()
        calculator = CalculatorTool()

        agent = ReactAgent(llm_client=llm_client, tools=[calculator], max_iterations=5)

        result = await agent.solve("如果一个产品原价 200 元，打 8 折后是多少钱？")

        assert result.success
        assert "160" in result.answer or "一百六" in result.answer


if __name__ == "__main__":
    # 运行单个测试
    pytest.main([__file__, "-v", "-s"])
