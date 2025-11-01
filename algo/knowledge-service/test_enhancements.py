#!/usr/bin/env python3
"""
测试增强功能脚本

验证所有13个优化功能是否正常工作
"""

import asyncio
from datetime import datetime

import httpx

BASE_URL = "http://localhost:8006"


async def test_enhanced_index_build():
    """测试增强版索引构建"""
    print("\n=== 测试 1: 增强版索引构建 ===")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 准备测试数据
        request_data = {
            "document_id": f"test_doc_{int(datetime.now().timestamp())}",
            "chunks": [
                {
                    "chunk_id": "chunk1",
                    "content": "Apple Inc. was founded by Steve Jobs in 1976. The company is headquartered in Cupertino, California.",
                },
                {
                    "chunk_id": "chunk2",
                    "content": "Steve Jobs served as CEO of Apple. He introduced the iPhone in 2007.",
                },
            ],
            "domain": "tech",
            "use_gds": False,  # 简化版社区检测
            "enable_entity_linking": True,
            "enable_temporal": False,
        }

        response = await client.post(f"{BASE_URL}/api/v1/enhanced/build-index", json=request_data)

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("✅ 索引构建成功")
            print(f"   - 实体数: {result['entities_count']}")
            print(f"   - 关系数: {result['relations_count']}")
            print(f"   - 社区数: {result['communities_count']}")
            print(f"   - 耗时: {result['duration_seconds']:.2f}s")
            print(f"   - 优化启用: {result['enhancements']}")
            return result["document_id"]
        else:
            print(f"❌ 索引构建失败: {response.text}")
            return None


async def test_cache_stats():
    """测试缓存统计"""
    print("\n=== 测试 2: LLM 缓存统计 ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/enhanced/cache/stats")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print("✅ 缓存统计获取成功")
            print(f"   - 命中次数: {stats['hit_count']}")
            print(f"   - 未命中次数: {stats['miss_count']}")
            print(f"   - 命中率: {stats['hit_rate']:.2%}")
        else:
            print(f"❌ 获取失败: {response.text}")


async def test_model_info():
    """测试模型信息"""
    print("\n=== 测试 3: LLM 模型信息 ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/enhanced/model/info")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            info = response.json()
            print("✅ 模型信息获取成功")
            print(f"   - 当前模型: {info['model']}")
            print(f"   - Prompt 价格: ${info['prompt_price_per_1k']}/1K tokens")
            print(f"   - Completion 价格: ${info['completion_price_per_1k']}/1K tokens")
        else:
            print(f"❌ 获取失败: {response.text}")


async def test_entity_linking(document_ids):
    """测试实体链接"""
    print("\n=== 测试 4: 实体链接 ===")

    if not document_ids or len(document_ids) < 2:
        print("⚠️  需要至少2个文档才能测试实体链接")
        return

    async with httpx.AsyncClient(timeout=60.0) as client:
        request_data = {"document_ids": document_ids, "method": "hybrid"}

        response = await client.post(
            f"{BASE_URL}/api/v1/enhanced/entity-linking", json=request_data
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("✅ 实体链接成功")
            print(f"   - 处理文档数: {result['documents_processed']}")
            print(f"   - 合并实体数: {result['total_merged']}")
        else:
            print(f"❌ 链接失败: {response.text}")


async def test_temporal_query():
    """测试时序查询"""
    print("\n=== 测试 5: 时序图谱查询 ===")

    async with httpx.AsyncClient() as client:
        request_data = {
            "entity_text": "Steve Jobs",
            "timestamp": "2010-01-01T00:00:00Z",
            "max_depth": 2,
        }

        response = await client.post(
            f"{BASE_URL}/api/v1/enhanced/temporal/query", json=request_data
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result["found"]:
                print("✅ 时序查询成功")
                print(f"   - 实体: {result['entity']['text']}")
                print(f"   - 时间点: {result['timestamp']}")
                print(f"   - 关系数: {result['relations_count']}")
            else:
                print("⚠️  实体未找到")
        else:
            print(f"❌ 查询失败: {response.text}")


async def test_service_stats():
    """测试服务统计"""
    print("\n=== 测试 6: 服务统计信息 ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/enhanced/stats")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print("✅ 服务统计获取成功")
            print(f"   - 缓存命中率: {stats['cache'].get('hit_rate', 0):.2%}")
            print(f"   - 降级组件数: {len(stats['fallback'].get('degraded_components', {}))}")
            print(f"   - 当前模型: {stats['llm_model']['model']}")
        else:
            print(f"❌ 获取失败: {response.text}")


async def test_model_downgrade():
    """测试模型降级"""
    print("\n=== 测试 7: LLM 模型降级 ===")

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/api/v1/enhanced/model/downgrade")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ 模型降级成功")
                print(f"   - 新模型: {result['new_model']}")
            else:
                print(f"⚠️  {result['message']}")
        else:
            print(f"❌ 降级失败: {response.text}")


async def test_prometheus_metrics():
    """测试 Prometheus 指标"""
    print("\n=== 测试 8: Prometheus 指标 ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/metrics")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            metrics = response.text
            print("✅ 指标导出成功")

            # 检查关键指标
            key_metrics = [
                "llm_requests_total",
                "llm_cost_usd_total",
                "cache_hit_rate",
                "entity_extraction_total",
                "retrieval_requests_total",
            ]

            found_metrics = []
            for metric in key_metrics:
                if metric in metrics:
                    found_metrics.append(metric)

            print(f"   - 找到指标: {len(found_metrics)}/{len(key_metrics)}")
            print(f"   - 指标列表: {', '.join(found_metrics)}")
        else:
            print(f"❌ 获取失败: {response.text}")


async def test_health():
    """测试健康检查"""
    print("\n=== 测试 9: 健康检查 ===")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            health = response.json()
            print(f"✅ 服务健康: {health['status']}")
            print(f"   - Neo4j: {health['dependencies']['neo4j'].get('healthy', False)}")
            print(f"   - Redis: {health['dependencies'].get('redis', {}).get('healthy', False)}")
        else:
            print(f"❌ 健康检查失败: {response.text}")


async def main():
    """主测试函数"""
    print("=" * 60)
    print("Knowledge Service 增强功能测试")
    print("=" * 60)

    try:
        # 测试 1: 健康检查
        await test_health()

        # 测试 2: 构建索引
        doc_id = await test_enhanced_index_build()

        # 测试 3: 缓存统计
        await test_cache_stats()

        # 测试 4: 模型信息
        await test_model_info()

        # 测试 5: 服务统计
        await test_service_stats()

        # 测试 6: Prometheus 指标
        await test_prometheus_metrics()

        # 测试 7: 模型降级
        await test_model_downgrade()

        # 如果有多个文档，测试实体链接
        if doc_id:
            # 构建第二个文档
            doc_id2 = await test_enhanced_index_build()
            if doc_id2:
                await test_entity_linking([doc_id, doc_id2])

        # 测试 8: 时序查询
        await test_temporal_query()

        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
