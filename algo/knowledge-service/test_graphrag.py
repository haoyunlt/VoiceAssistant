"""
GraphRAG功能测试脚本

测试LLM实体提取、分层索引、混合检索和增量更新功能
"""

import asyncio
import sys

import httpx

# 服务地址
BASE_URL = "http://localhost:8006"


async def test_build_index():
    """测试构建分层索引"""
    print("\n" + "=" * 50)
    print("测试1: 构建GraphRAG分层索引")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=60.0) as client:
        request_data = {
            "document_id": "apple_history",
            "chunks": [
                {
                    "chunk_id": "chunk_1",
                    "content": "Apple Inc. was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976 in Los Altos, California. The company initially started in Jobs' parents' garage.",
                },
                {
                    "chunk_id": "chunk_2",
                    "content": "In 1977, Apple introduced the Apple II, one of the first highly successful mass-produced microcomputers. The company went public in 1980.",
                },
                {
                    "chunk_id": "chunk_3",
                    "content": "Steve Jobs was ousted from Apple in 1985 but returned in 1997 to save the company from bankruptcy. He introduced revolutionary products like the iMac, iPod, iPhone, and iPad.",
                },
                {
                    "chunk_id": "chunk_4",
                    "content": "In 2011, Tim Cook became CEO after Steve Jobs' resignation due to health issues. Under Cook's leadership, Apple became the first trillion-dollar company in 2018.",
                },
            ],
            "domain": "tech",
        }

        print(f"\n发送请求到: {BASE_URL}/api/v1/graphrag/build-index")
        print(f"文档ID: {request_data['document_id']}")
        print(f"文本块数: {len(request_data['chunks'])}")

        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/graphrag/build-index",
                json=request_data,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

            print("\n✅ 索引构建成功!")
            print(f"  实体数: {result.get('entities_count', 0)}")
            print(f"  关系数: {result.get('relations_count', 0)}")
            print(f"  社区数: {result.get('communities_count', 0)}")
            print(f"  耗时: {result.get('elapsed_seconds', 0):.2f}秒")
            print("\n📝 全局摘要:")
            print(f"  {result.get('global_summary', 'N/A')}")

            return True

        except httpx.HTTPError as e:
            print(f"\n❌ HTTP错误: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"  响应: {e.response.text}")
            return False
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            return False


async def test_hybrid_retrieval():
    """测试混合检索"""
    print("\n" + "=" * 50)
    print("测试2: 混合检索")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        test_queries = [
            "Who founded Apple?",
            "When did Apple go public?",
            "What happened to Steve Jobs in 1985?",
            "Who is the current CEO of Apple?",
        ]

        for query in test_queries:
            print(f"\n🔍 查询: {query}")

            request_data = {
                "query": query,
                "top_k": 3,
                "mode": "hybrid",
                "enable_rerank": True,
            }

            try:
                response = await client.post(
                    f"{BASE_URL}/api/v1/graphrag/retrieve/hybrid",
                    json=request_data,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                print(f"  ✅ 找到 {result.get('total', 0)} 个结果")

                for i, item in enumerate(result.get("results", [])[:3], 1):
                    print(f"\n  结果 {i}:")
                    print(f"    得分: {item.get('score', 0):.3f}")
                    print(f"    方法: {item.get('method', 'N/A')}")
                    print(f"    内容: {item.get('content', '')[:100]}...")

            except httpx.HTTPError as e:
                print(f"  ❌ HTTP错误: {e}")
            except Exception as e:
                print(f"  ❌ 错误: {e}")

            await asyncio.sleep(1)  # 避免频繁请求


async def test_global_query():
    """测试全局查询"""
    print("\n" + "=" * 50)
    print("测试3: 全局查询（基于社区摘要）")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        request_data = {
            "query": "What is the main story about Apple?",
            "top_k": 3,
        }

        print(f"\n🌍 全局查询: {request_data['query']}")

        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/graphrag/query/global",
                json=request_data,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            print(f"\n✅ 找到 {len(result.get('relevant_communities', []))} 个相关社区")
            print(f"   （总共 {result.get('total_communities', 0)} 个社区）")

            for i, community in enumerate(result.get("relevant_communities", []), 1):
                print(f"\n社区 {i}:")
                print(f"  大小: {community.get('size', 0)} 个实体")
                print(f"  相关性得分: {community.get('relevance_score', 0)}")
                print(f"  关键词: {', '.join(community.get('keywords', []))}")
                print(f"  摘要: {community.get('summary', '')}")

            return True

        except httpx.HTTPError as e:
            print(f"\n❌ HTTP错误: {e}")
            return False
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            return False


async def test_incremental_update():
    """测试增量更新"""
    print("\n" + "=" * 50)
    print("测试4: 增量更新")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 更新文档
        request_data = {
            "document_id": "apple_history",
            "change_type": "update",
            "content": "Updated: Apple Inc. continues to innovate under Tim Cook's leadership, launching new products like Apple Vision Pro in 2023.",
            "domain": "tech",
        }

        print(f"\n⚡ 更新文档: {request_data['document_id']}")
        print(f"   变更类型: {request_data['change_type']}")

        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/graphrag/update/incremental",
                json=request_data,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            print("\n✅ 增量更新成功!")
            details = result.get("details", {})
            print(f"  新增实体: {details.get('entities_added', 0)}")
            print(f"  删除实体: {details.get('entities_removed', 0)}")
            print(f"  不变实体: {details.get('entities_unchanged', 0)}")
            print(f"  耗时: {details.get('elapsed_seconds', 0):.2f}秒")

            return True

        except httpx.HTTPError as e:
            print(f"\n❌ HTTP错误: {e}")
            return False
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            return False


async def test_stats():
    """测试索引统计"""
    print("\n" + "=" * 50)
    print("测试5: 索引统计")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=10.0) as client:
        print("\n📊 获取索引统计...")

        try:
            response = await client.get(f"{BASE_URL}/api/v1/graphrag/stats")
            response.raise_for_status()
            result = response.json()

            stats = result.get("stats", {})

            print("\n✅ 统计信息:")
            print("\n  节点（按类型）:")
            for node_stat in stats.get("nodes", [])[:10]:
                print(f"    - {node_stat['label']}: {node_stat['count']}")

            print("\n  关系（按类型）:")
            for rel_stat in stats.get("relationships", [])[:10]:
                print(f"    - {rel_stat['type']}: {rel_stat['count']}")

            print(f"\n  文档总数: {stats.get('documents', 0)}")

            return True

        except httpx.HTTPError as e:
            print(f"\n❌ HTTP错误: {e}")
            return False
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 50)
    print("GraphRAG 功能测试")
    print("=" * 50)
    print(f"\n服务地址: {BASE_URL}")
    print("确保服务正在运行: make run-dev")

    # 检查服务健康状态
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/health")
            response.raise_for_status()
            print("\n✅ 服务健康检查通过")
    except Exception as e:
        print(f"\n❌ 服务不可用: {e}")
        print("请先启动服务: cd algo/knowledge-service && make run-dev")
        return

    # 运行测试
    results = {}

    results["build_index"] = await test_build_index()
    await asyncio.sleep(2)

    results["hybrid_retrieval"] = await test_hybrid_retrieval()
    await asyncio.sleep(2)

    results["global_query"] = await test_global_query()
    await asyncio.sleep(2)

    results["incremental_update"] = await test_incremental_update()
    await asyncio.sleep(2)

    results["stats"] = await test_stats()

    # 汇总结果
    print("\n" + "=" * 50)
    print("测试汇总")
    print("=" * 50)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n通过: {passed}/{total}")

    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")

    if passed == total:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
