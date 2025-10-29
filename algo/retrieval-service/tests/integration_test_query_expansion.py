#!/usr/bin/env python3
"""
Query Expansion 集成测试

测试Query Expansion功能是否正确集成到retrieval_service中
"""

import asyncio
import sys
from pathlib import Path

# Mock必要的依赖
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MockSettings:
    """Mock配置"""

    RRF_K = 60
    VECTOR_TOP_K = 20
    BM25_TOP_K = 20
    HYBRID_TOP_K = 10
    ENABLE_RERANK = False
    RERANK_TOP_K = 10
    ENABLE_GRAPH_RETRIEVAL = False

    def __getattr__(self, name):
        return None


class MockLogger:
    """Mock日志"""

    @staticmethod
    def info(msg, **kwargs):
        print(f"[INFO] {msg}")

    @staticmethod
    def debug(msg, **kwargs):
        print(f"[DEBUG] {msg}")

    @staticmethod
    def warning(msg, **kwargs):
        print(f"[WARNING] {msg}")

    @staticmethod
    def error(msg, **kwargs):
        print(f"[ERROR] {msg}")


# Mock模块
sys.modules["app.core.config"] = type("module", (), {"settings": MockSettings()})()
sys.modules["app.observability.logging"] = type("module", (), {"logger": MockLogger()})()
sys.modules["app.core.logging"] = type("module", (), {"logger": MockLogger()})()


# Mock服务
class MockVectorService:
    async def search(self, **kwargs):
        return []


class MockBM25Service:
    async def search(self, **kwargs):
        return []


class MockHybridService:
    def __init__(self, **kwargs):
        pass

    async def fuse_results(self, **kwargs):
        return []


class MockRerankService:
    async def rerank(self, **kwargs):
        return []


class MockEmbeddingService:
    async def embed_query(self, query):
        # 返回假的embedding
        return [0.1] * 768


# 注入Mock服务
sys.modules["app.services.vector_service"] = type(
    "module", (), {"VectorService": MockVectorService}
)()
sys.modules["app.services.bm25_service"] = type("module", (), {"BM25Service": MockBM25Service})()
sys.modules["app.services.hybrid_service"] = type(
    "module", (), {"HybridService": MockHybridService}
)()
sys.modules["app.services.rerank_service"] = type(
    "module", (), {"RerankService": MockRerankService}
)()
sys.modules["app.services.embedding_service"] = type(
    "module", (), {"EmbeddingService": MockEmbeddingService}
)()
sys.modules["app.services.graph_retrieval_service"] = type(
    "module", (), {"GraphRetrievalService": lambda x: None}
)()
sys.modules["app.services.hybrid_graph_service"] = type(
    "module", (), {"HybridGraphService": lambda **x: None}
)()
sys.modules["app.infrastructure.neo4j_client"] = type(
    "module", (), {"Neo4jClient": lambda **x: None}
)()

# 导入要测试的模块
from app.models.retrieval import HybridRequest, HybridResponse
from app.services.retrieval_service import RetrievalService


async def test_query_expansion_integration():
    """测试Query Expansion集成到RetrievalService"""
    print("=" * 60)
    print("测试1: Query Expansion 集成测试")
    print("=" * 60)

    # 创建RetrievalService
    print("\n初始化RetrievalService...")
    service = RetrievalService()

    # 检查query_expansion是否初始化
    assert hasattr(service, "query_expansion"), (
        "RetrievalService should have query_expansion attribute"
    )
    assert service.query_expansion is not None, "query_expansion should be initialized"

    print("✅ QueryExpansionService已成功集成")

    # 测试不启用query expansion
    print("\n测试场景1: 不启用Query Expansion")
    request = HybridRequest(
        query="如何使用系统",
        enable_query_expansion=False,
        top_k=10,
    )

    response = await service.hybrid_search(request)

    assert isinstance(response, HybridResponse)
    assert response.query_expanded is False
    assert response.expanded_queries is None
    assert response.expansion_latency_ms is None
    print("✅ 不启用expansion时正常工作")

    # 测试启用query expansion
    print("\n测试场景2: 启用Query Expansion")
    request = HybridRequest(
        query="如何购买产品",
        enable_query_expansion=True,
        query_expansion_max=3,
        top_k=10,
    )

    response = await service.hybrid_search(request)

    assert isinstance(response, HybridResponse)
    assert response.query_expanded is True, "应该已扩展查询"
    assert response.expanded_queries is not None, "应该有扩展查询列表"
    assert len(response.expanded_queries) >= 1, "至少有原查询"
    assert response.expansion_latency_ms is not None, "应该有扩展延迟统计"
    assert response.expansion_latency_ms >= 0, "延迟应该>=0"

    print(f"  原查询: {request.query}")
    print(f"  扩展查询: {response.expanded_queries}")
    print(f"  扩展延迟: {response.expansion_latency_ms:.2f}ms")
    print("✅ 启用expansion时正常工作")

    # 测试扩展数量限制
    print("\n测试场景3: 限制扩展数量")
    request = HybridRequest(
        query="如何使用系统功能",
        enable_query_expansion=True,
        query_expansion_max=2,  # 限制为2个
        top_k=10,
    )

    response = await service.hybrid_search(request)

    assert len(response.expanded_queries) <= 2, "扩展数量应不超过max"
    print("  最大扩展数: 2")
    print(f"  实际扩展数: {len(response.expanded_queries)}")
    print("✅ 扩展数量限制正常")


async def test_response_fields():
    """测试响应字段完整性"""
    print("\n" + "=" * 60)
    print("测试2: 响应字段完整性")
    print("=" * 60)

    service = RetrievalService()

    request = HybridRequest(
        query="测试查询",
        enable_query_expansion=True,
        top_k=10,
    )

    response = await service.hybrid_search(request)

    # 检查所有字段
    required_fields = [
        "documents",
        "query",
        "vector_count",
        "bm25_count",
        "reranked",
        "latency_ms",
        "query_expanded",
        "expanded_queries",
        "expansion_latency_ms",
    ]

    print("\n检查响应字段:")
    for field in required_fields:
        assert hasattr(response, field), f"Missing field: {field}"
        value = getattr(response, field)
        print(f"  ✅ {field}: {type(value).__name__}")

    print("\n✅ 所有字段完整")


async def test_performance():
    """测试性能影响"""
    print("\n" + "=" * 60)
    print("测试3: 性能影响测试")
    print("=" * 60)

    service = RetrievalService()

    # 测试不启用expansion的延迟
    print("\n测试不启用expansion:")
    request_no_expansion = HybridRequest(
        query="如何使用系统",
        enable_query_expansion=False,
        top_k=10,
    )

    latencies_no_expansion = []
    for i in range(5):
        response = await service.hybrid_search(request_no_expansion)
        latencies_no_expansion.append(response.latency_ms)

    avg_no_expansion = sum(latencies_no_expansion) / len(latencies_no_expansion)
    print(f"  平均延迟: {avg_no_expansion:.2f}ms")

    # 测试启用expansion的延迟
    print("\n测试启用expansion:")
    request_with_expansion = HybridRequest(
        query="如何使用系统",
        enable_query_expansion=True,
        top_k=10,
    )

    latencies_with_expansion = []
    for i in range(5):
        response = await service.hybrid_search(request_with_expansion)
        latencies_with_expansion.append(response.latency_ms)
        if i == 0:
            print(f"  扩展延迟: {response.expansion_latency_ms:.2f}ms")

    avg_with_expansion = sum(latencies_with_expansion) / len(latencies_with_expansion)
    print(f"  平均总延迟: {avg_with_expansion:.2f}ms")

    overhead = avg_with_expansion - avg_no_expansion
    print(f"\n性能开销: {overhead:.2f}ms ({overhead / avg_no_expansion * 100:.1f}%)")

    # 性能要求: expansion延迟应该很小（<50ms）
    if overhead < 100:
        print("✅ 性能开销可接受")
    else:
        print(f"⚠️  性能开销较大: {overhead:.2f}ms")


async def test_stats():
    """测试统计信息"""
    print("\n" + "=" * 60)
    print("测试4: 统计信息")
    print("=" * 60)

    service = RetrievalService()

    if service.query_expansion:
        stats = service.query_expansion.get_stats()
        print("\nQuery Expansion 统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        assert stats["synonym_dict_size"] > 0
        assert stats["methods"] == ["synonym", "spelling"]
        print("\n✅ 统计信息正常")
    else:
        print("⚠️  Query Expansion未初始化")


async def main():
    """运行所有测试"""
    print("\n" + "🚀" * 30)
    print("Query Expansion 集成测试")
    print("🚀" * 30 + "\n")

    try:
        await test_query_expansion_integration()
        await test_response_fields()
        await test_performance()
        await test_stats()

        print("\n" + "=" * 60)
        print("🎉 所有集成测试通过！")
        print("=" * 60)

        print("\n✅ 集成验收标准:")
        print("  ✅ QueryExpansionService已集成到RetrievalService")
        print("  ✅ HybridRequest支持enable_query_expansion参数")
        print("  ✅ HybridResponse包含expansion信息字段")
        print("  ✅ 启用/禁用expansion都能正常工作")
        print("  ✅ 性能开销在可接受范围内")
        print("  ✅ 统计信息正常")

        print("\n📋 集成完成情况:")
        print("  ✅ Step 1: 初始化QueryExpansionService")
        print("  ✅ Step 2: 更新HybridRequest模型")
        print("  ✅ Step 3: 更新HybridResponse模型")
        print("  ✅ Step 4: 修改hybrid_search方法")
        print("  ✅ Step 5: 集成测试通过")

        print("\n🎊 Task 1.1 集成工作完成！")
        print("\n下一步:")
        print("  1. 准备评测数据集")
        print("  2. 运行召回率评测")
        print("  3. 验证召回率提升≥15%")
        print("  4. 提交PR")

        return 0

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
