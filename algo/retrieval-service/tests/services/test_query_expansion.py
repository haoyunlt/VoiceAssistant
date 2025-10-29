"""
Query Expansion Service 单元测试
"""

import json

import pytest
from app.services.query.expansion_service import ExpandedQuery, QueryExpansionService


@pytest.fixture
def expansion_service():
    """创建测试用的扩展服务"""
    return QueryExpansionService(
        methods=["synonym", "spelling"],
        max_expansions=3,
        llm_endpoint=None,  # 不启用LLM (单元测试)
    )


@pytest.fixture
def expansion_service_with_llm():
    """创建带LLM的扩展服务（集成测试用）"""
    return QueryExpansionService(
        methods=["synonym", "spelling", "llm"],
        max_expansions=5,
        llm_endpoint="http://localhost:8000",  # Mock endpoint
        llm_model="qwen-7b",
    )


class TestQueryExpansionService:
    """Query Expansion Service 测试类"""

    def test_initialization(self, expansion_service):
        """测试服务初始化"""
        assert expansion_service.methods == ["synonym", "spelling"]
        assert expansion_service.max_expansions == 3
        assert len(expansion_service.synonym_dict) > 0
        assert len(expansion_service.spelling_corrections) > 0

    @pytest.mark.asyncio
    async def test_expand_basic(self, expansion_service):
        """测试基础扩展功能"""
        query = "如何使用系统"
        result = await expansion_service.expand(query)

        assert isinstance(result, ExpandedQuery)
        assert result.original == query
        assert len(result.expanded) >= 1
        assert result.expanded[0] == query  # 原查询始终排第一
        assert len(result.weights) == len(result.expanded)
        assert result.weights[0] == 1.0  # 原查询权重最高
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_synonym_expansion(self, expansion_service):
        """测试同义词扩展"""
        query = "如何购买"
        result = await expansion_service.expand(query)

        # 应该包含原查询
        assert query in result.expanded

        # 应该有扩展（如 "如何买"、"如何下单" 等）
        # 注意：具体扩展结果取决于同义词词典
        assert len(result.expanded) > 1

        # 打印结果以便调试
        print(f"\nOriginal: {query}")
        print(f"Expanded: {result.expanded}")

    @pytest.mark.asyncio
    async def test_spelling_correction(self, expansion_service):
        """测试拼写纠错"""
        query = "帐号登陆"  # 错误拼写
        result = await expansion_service.expand(query)

        # 应该包含纠错后的版本 "账号登录"
        corrected_queries = [q for q in result.expanded if "账号" in q or "登录" in q]
        assert len(corrected_queries) > 0

        print(f"\nOriginal: {query}")
        print(f"Expanded: {result.expanded}")

    @pytest.mark.asyncio
    async def test_max_expansions_limit(self, expansion_service):
        """测试扩展数量限制"""
        query = "如何使用系统"
        result = await expansion_service.expand(query)

        # 不应超过max_expansions
        assert len(result.expanded) <= expansion_service.max_expansions

    @pytest.mark.asyncio
    async def test_empty_query(self, expansion_service):
        """测试空查询"""
        query = ""
        result = await expansion_service.expand(query)

        # 应该返回空查询本身
        assert result.original == ""
        assert len(result.expanded) >= 1
        assert result.expanded[0] == ""

    @pytest.mark.asyncio
    async def test_single_word_query(self, expansion_service):
        """测试单词查询"""
        query = "购买"
        result = await expansion_service.expand(query)

        # 应该有同义词扩展（如 "买"、"下单"）
        assert query in result.expanded
        assert len(result.expanded) > 1

        print(f"\nOriginal: {query}")
        print(f"Expanded: {result.expanded}")

    @pytest.mark.asyncio
    async def test_multi_word_query(self, expansion_service):
        """测试多词查询"""
        query = "如何购买产品"
        result = await expansion_service.expand(query)

        assert query in result.expanded
        # 应该有替换部分词的扩展
        assert len(result.expanded) > 1

    @pytest.mark.asyncio
    async def test_weights(self, expansion_service):
        """测试权重分配"""
        query = "如何使用"
        result = await expansion_service.expand(query)

        # 原查询权重最高
        assert result.weights[0] == 1.0

        # 其他扩展权重应该递减
        for i in range(1, len(result.weights)):
            assert result.weights[i] < 1.0
            assert result.weights[i] > 0

    @pytest.mark.asyncio
    async def test_batch_expansion(self, expansion_service):
        """测试批量扩展"""
        queries = ["如何购买", "怎么使用", "什么是系统"]
        results = await expansion_service.expand_batch(queries)

        assert len(results) == len(queries)
        for i, result in enumerate(results):
            assert result.original == queries[i]
            assert len(result.expanded) >= 1

    def test_stats(self, expansion_service):
        """测试统计信息"""
        stats = expansion_service.get_stats()

        assert "methods" in stats
        assert "max_expansions" in stats
        assert "synonym_dict_size" in stats
        assert "spelling_dict_size" in stats
        assert "llm_enabled" in stats

        assert stats["methods"] == ["synonym", "spelling"]
        assert stats["max_expansions"] == 3
        assert stats["synonym_dict_size"] > 0
        assert stats["spelling_dict_size"] > 0
        assert stats["llm_enabled"] is False

    @pytest.mark.asyncio
    async def test_no_duplicate_expansions(self, expansion_service):
        """测试扩展结果去重"""
        query = "购买"
        result = await expansion_service.expand(query)

        # 不应该有重复的扩展
        assert len(result.expanded) == len(set(result.expanded))

    @pytest.mark.asyncio
    async def test_performance(self, expansion_service):
        """测试性能要求：P95延迟 < 50ms"""
        query = "如何使用系统功能"

        # 运行10次测试
        latencies = []
        for _ in range(10):
            result = await expansion_service.expand(query)
            latencies.append(result.latency_ms)

        # 计算P95
        latencies.sorted()
        p95_latency = latencies[int(len(latencies) * 0.95)]

        print(f"\nPerformance test - P95 latency: {p95_latency:.2f}ms")

        # 验收标准：P95 < 50ms（不依赖LLM）
        assert p95_latency < 50, f"P95 latency {p95_latency:.2f}ms exceeds 50ms"

    @pytest.mark.asyncio
    async def test_custom_synonym_dict(self, tmp_path):
        """测试自定义同义词词典"""
        # 创建临时词典文件
        custom_dict = {"测试": ["test", "验证"]}
        dict_file = tmp_path / "custom_synonyms.json"

        with open(dict_file, "w", encoding="utf-8") as f:
            json.dump(custom_dict, f, ensure_ascii=False)

        # 创建带自定义词典的服务
        service = QueryExpansionService(
            methods=["synonym"],
            max_expansions=3,
            synonym_dict_path=str(dict_file),
        )

        # 测试自定义同义词
        query = "测试功能"
        result = await service.expand(query)

        # 应该包含自定义同义词的扩展
        assert any("test" in q or "验证" in q for q in result.expanded)


class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_very_long_query(self, expansion_service):
        """测试超长查询"""
        query = "如何 " + "使用 " * 50 + "系统"  # 很长的查询
        result = await expansion_service.expand(query)

        # 应该能正常处理，不报错
        assert result.original == query
        assert len(result.expanded) >= 1

    @pytest.mark.asyncio
    async def test_special_characters(self, expansion_service):
        """测试特殊字符"""
        query = "如何@#$%使用&*系统?"
        result = await expansion_service.expand(query)

        # 应该能处理特殊字符
        assert result.original == query
        assert len(result.expanded) >= 1

    @pytest.mark.asyncio
    async def test_mixed_language(self, expansion_service):
        """测试中英混合"""
        query = "how to 使用 API 接口"
        result = await expansion_service.expand(query)

        assert result.original == query
        assert len(result.expanded) >= 1

    @pytest.mark.asyncio
    async def test_numbers(self, expansion_service):
        """测试包含数字的查询"""
        query = "2024年如何购买产品"
        result = await expansion_service.expand(query)

        assert result.original == query
        assert len(result.expanded) >= 1


# 集成测试（需要Mock LLM endpoint）
class TestLLMIntegration:
    """LLM集成测试（需要Mock或实际endpoint）"""

    @pytest.mark.skip(reason="需要LLM endpoint")
    @pytest.mark.asyncio
    async def test_llm_rewrite(self, expansion_service_with_llm):
        """测试LLM改写（需要实际endpoint）"""
        query = "如何使用系统"
        result = await expansion_service_with_llm.expand(query, enable_llm=True)

        # 应该有LLM生成的改写
        assert len(result.expanded) > 1
        assert "llm" in result.method


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
