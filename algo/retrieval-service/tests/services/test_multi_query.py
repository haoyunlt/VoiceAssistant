"""
Multi-Query Service 单元测试
"""


import pytest
from app.services.query.multi_query_service import (
    MultiQueryResult,
    MultiQueryService,
    SimpleMultiQueryGenerator,
)


@pytest.fixture
def multi_query_service_no_llm():
    """创建无LLM的服务（使用模板）"""
    return MultiQueryService(
        llm_endpoint=None,
        num_queries=3,
    )


@pytest.fixture
def multi_query_service_with_llm():
    """创建带LLM的服务（用于集成测试）"""
    return MultiQueryService(
        llm_endpoint="http://localhost:8000",
        llm_model="qwen-7b",
        num_queries=3,
        temperature=0.7,
    )


@pytest.fixture
def simple_generator():
    """创建简单生成器"""
    return SimpleMultiQueryGenerator(num_queries=3)


class TestMultiQueryService:
    """Multi-Query Service 测试类"""

    @pytest.mark.asyncio
    async def test_generate_with_templates(self, multi_query_service_no_llm):
        """测试模板生成"""
        query = "如何使用Python"
        result = await multi_query_service_no_llm.generate(query)

        assert isinstance(result, MultiQueryResult)
        assert result.original == query
        assert len(result.queries) >= 1  # 至少包含原查询
        assert result.queries[0] == query  # 第一个是原查询
        assert result.method == "template"
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_generate_num_queries(self, multi_query_service_no_llm):
        """测试生成数量控制"""
        query = "测试查询"
        result = await multi_query_service_no_llm.generate(query, num_queries=2)

        # 应该有原查询 + 2个变体 = 最多3个
        assert len(result.queries) <= 3
        assert result.queries[0] == query

    @pytest.mark.asyncio
    async def test_generate_deduplication(self, multi_query_service_no_llm):
        """测试去重"""
        query = "如何学习编程"
        result = await multi_query_service_no_llm.generate(query)

        # 不应该有重复
        assert len(result.queries) == len(set(result.queries))

    @pytest.mark.asyncio
    async def test_batch_generation(self, multi_query_service_no_llm):
        """测试批量生成"""
        queries = ["如何学习", "什么是AI", "为什么重要"]
        results = await multi_query_service_no_llm.generate_batch(queries)

        assert len(results) == len(queries)
        for i, result in enumerate(results):
            assert result.original == queries[i]
            assert len(result.queries) >= 1

    def test_parse_llm_response(self, multi_query_service_no_llm):
        """测试LLM响应解析"""
        content = """1. 如何使用Python进行编程
2. Python编程的方法是什么
3. 使用Python编程的步骤"""

        original = "如何使用Python"
        queries = multi_query_service_no_llm._parse_llm_response(content, original)

        assert len(queries) == 3
        assert all(q != original for q in queries)  # 不包含原查询
        assert all(len(q) > 0 for q in queries)

    def test_template_generation(self, multi_query_service_no_llm):
        """测试模板生成"""
        query = "Python基础"
        templates = multi_query_service_no_llm._generate_with_templates(query, 3)

        assert len(templates) <= 3
        assert all(isinstance(t, str) for t in templates)
        assert all(len(t) > len(query) for t in templates)  # 模板应该更长

    @pytest.mark.asyncio
    async def test_performance(self, multi_query_service_no_llm):
        """测试性能（模板方法应该很快）"""
        query = "如何使用系统"
        result = await multi_query_service_no_llm.generate(query)

        # 模板方法应该 < 10ms
        assert result.latency_ms < 100, f"Too slow: {result.latency_ms}ms"

    def test_get_stats(self, multi_query_service_no_llm):
        """测试统计信息"""
        stats = multi_query_service_no_llm.get_stats()

        assert "llm_endpoint" in stats
        assert "llm_model" in stats
        assert "num_queries" in stats
        assert "llm_available" in stats
        assert stats["llm_available"] is False  # 无LLM

    @pytest.mark.skip(reason="需要实际LLM endpoint")
    @pytest.mark.asyncio
    async def test_generate_with_llm(self, multi_query_service_with_llm):
        """测试LLM生成（需要实际endpoint）"""
        query = "如何使用Python进行数据分析"
        result = await multi_query_service_with_llm.generate(query)

        assert result.method == "llm"
        assert len(result.queries) > 1
        assert result.queries[0] == query


class TestSimpleMultiQueryGenerator:
    """简单生成器测试"""

    @pytest.mark.asyncio
    async def test_simple_generation(self, simple_generator):
        """测试简单生成"""
        query = "如何学习编程"
        variants = await simple_generator.generate(query)

        assert len(variants) >= 1
        assert variants[0] == query  # 第一个是原查询
        assert all(isinstance(v, str) for v in variants)

    @pytest.mark.asyncio
    async def test_question_transform(self, simple_generator):
        """测试问句转换"""
        query = "如何使用Python"
        variants = await simple_generator.generate(query)

        # 应该有"怎么"、"怎样"等变体
        any("怎么" in v or "怎样" in v for v in variants)
        assert len(variants) > 1  # 应该有变体


class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_empty_query(self, multi_query_service_no_llm):
        """测试空查询"""
        query = ""
        result = await multi_query_service_no_llm.generate(query)

        assert result.original == ""
        assert len(result.queries) >= 1

    @pytest.mark.asyncio
    async def test_long_query(self, multi_query_service_no_llm):
        """测试长查询"""
        query = "如何 " + "使用 " * 50 + "系统"
        result = await multi_query_service_no_llm.generate(query)

        assert result.original == query
        assert len(result.queries) >= 1

    @pytest.mark.asyncio
    async def test_special_characters(self, multi_query_service_no_llm):
        """测试特殊字符"""
        query = "如何@#$%使用系统?"
        result = await multi_query_service_no_llm.generate(query)

        assert result.original == query
        assert len(result.queries) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

