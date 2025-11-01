"""
两级向量缓存演示

展示如何使用 L1 (内存) + L2 (Redis) 缓存来加速向量化
"""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_basic_cache():
    """基础缓存演示"""
    logger.info("=== Demo 1: Basic Two-Level Cache ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import VectorCache

    # 1. 初始化组件
    redis_client = await redis.from_url("redis://localhost:6379/0")
    embedder = BGE_M3_Embedder()

    vector_cache = VectorCache(
        redis_client=redis_client,
        l1_max_size=100,  # 小容量用于演示
        l2_ttl=3600,      # 1小时
    )

    # 2. 测试文本
    texts = [
        "人工智能正在改变世界",
        "机器学习是AI的核心技术",
        "深度学习取得了突破性进展",
    ]

    # 3. 第一次请求 - 缓存未命中，需要计算
    logger.info("First request (cache miss):")
    start_time = time.time()

    for text in texts:
        vector = await vector_cache.get_or_compute(
            text=text,
            model="bge-m3",
            compute_fn=lambda t=text: embedder.embed(t),
        )
        logger.info(f"  - Vector dimension: {len(vector)}")

    first_duration = time.time() - start_time
    logger.info(f"⏱️  Duration: {first_duration:.3f}s\n")

    # 4. 第二次请求 - L1 缓存命中
    logger.info("Second request (L1 cache hit):")
    start_time = time.time()

    for text in texts:
        vector = await vector_cache.get_or_compute(
            text=text,
            model="bge-m3",
            compute_fn=lambda t=text: embedder.embed(t),
        )

    second_duration = time.time() - start_time
    logger.info(f"⏱️  Duration: {second_duration:.3f}s")
    logger.info(f"🚀 Speedup: {first_duration / second_duration:.1f}x\n")

    # 5. 查看缓存统计
    stats = vector_cache.get_stats()
    logger.info("📊 Cache Statistics:")
    logger.info(f"  L1 - Size: {stats['L1']['size']}, Hit Rate: {stats['L1']['hit_rate']:.2%}")
    logger.info(f"  L2 - Hits: {stats['L2']['hits']}, Hit Rate: {stats['L2']['hit_rate']:.2%}")
    logger.info(f"  Overall Hit Rate: {stats['overall']['hit_rate']:.2%}")
    logger.info(f"  Cache Efficiency: {stats['overall']['cache_efficiency']:.2%}\n")

    # 清理
    await redis_client.close()


async def demo_batch_cache():
    """批量缓存演示"""
    logger.info("=== Demo 2: Batch Cache with Partial Hits ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import VectorCache

    # 初始化
    redis_client = await redis.from_url("redis://localhost:6379/0")
    embedder = BGE_M3_Embedder()

    vector_cache = VectorCache(
        redis_client=redis_client,
        l1_max_size=1000,
        l2_ttl=3600,
    )

    # 测试数据
    all_texts = [
        "自然语言处理技术",
        "计算机视觉应用",
        "语音识别系统",
        "推荐算法优化",
        "数据挖掘方法",
    ]

    # 第一次：缓存部分文本
    logger.info("Step 1: Cache 3 texts")
    await vector_cache.get_batch_or_compute(
        texts=all_texts[:3],
        model="bge-m3",
        compute_fn=lambda texts: embedder.embed_batch(texts),
    )

    # 第二次：混合请求（部分命中，部分未命中）
    logger.info("\nStep 2: Mixed request (2 cached, 3 new)")
    start_time = time.time()

    vectors = await vector_cache.get_batch_or_compute(
        texts=all_texts,
        model="bge-m3",
        compute_fn=lambda texts: embedder.embed_batch(texts),
    )

    duration = time.time() - start_time
    logger.info(f"  Processed {len(vectors)} vectors in {duration:.3f}s")

    # 统计
    stats = vector_cache.get_stats()
    logger.info(f"\n📊 Final Stats:")
    logger.info(f"  Total Requests: {stats['overall']['total_requests']}")
    logger.info(f"  Total Hits: {stats['overall']['total_hits']}")
    logger.info(f"  Compute Count: {stats['overall']['compute_count']}")
    logger.info(f"  Overall Hit Rate: {stats['overall']['hit_rate']:.2%}\n")

    await redis_client.close()


async def demo_cached_embedder():
    """带缓存的 Embedder 演示"""
    logger.info("=== Demo 3: CachedEmbedder Wrapper ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import VectorCache
    from app.core.cached_embedder import CachedEmbedder

    # 初始化
    redis_client = await redis.from_url("redis://localhost:6379/0")

    # 原始 Embedder
    base_embedder = BGE_M3_Embedder()

    # 创建缓存
    vector_cache = VectorCache(
        redis_client=redis_client,
        l1_max_size=1000,
        l2_ttl=3600,
    )

    # 包装为带缓存的 Embedder
    cached_embedder = CachedEmbedder(
        embedder=base_embedder,
        vector_cache=vector_cache,
        model_name="bge-m3",
    )

    # 测试数据
    texts = [
        "深度学习模型训练",
        "神经网络架构搜索",
        "迁移学习应用",
        "强化学习算法",
        "联邦学习框架",
    ] * 2  # 重复两次

    # 使用带缓存的 Embedder
    logger.info("Processing 10 texts (5 unique, 5 duplicates)...")

    start_time = time.time()
    vectors = await cached_embedder.embed_batch(texts)
    duration = time.time() - start_time

    logger.info(f"⏱️  Duration: {duration:.3f}s")
    logger.info(f"  Processed {len(vectors)} vectors")

    # 查看统计
    stats = cached_embedder.get_cache_stats()
    logger.info(f"\n📊 Cache Stats:")
    logger.info(f"  Hit Rate: {stats['overall']['hit_rate']:.2%}")
    logger.info(f"  Compute Count: {stats['overall']['compute_count']} (expected: 5)")
    logger.info(f"  Cache Efficiency: {stats['overall']['cache_efficiency']:.2%}\n")

    await redis_client.close()


async def demo_cache_warmup():
    """缓存预热演示"""
    logger.info("=== Demo 4: Cache Warmup ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import VectorCache
    from app.core.cached_embedder import CachedEmbedder

    # 初始化
    redis_client = await redis.from_url("redis://localhost:6379/0")
    base_embedder = BGE_M3_Embedder()

    vector_cache = VectorCache(
        redis_client=redis_client,
        l1_max_size=1000,
        l2_ttl=3600,
    )

    cached_embedder = CachedEmbedder(
        embedder=base_embedder,
        vector_cache=vector_cache,
        model_name="bge-m3",
    )

    # 准备常用文本（如常见问题）
    common_texts = [
        "如何使用产品？",
        "价格是多少？",
        "有什么优惠活动？",
        "支持哪些支付方式？",
        "配送需要多长时间？",
        "如何申请退款？",
        "产品保修期多久？",
        "有什么售后服务？",
    ]

    # 预热缓存
    logger.info(f"Warming up cache with {len(common_texts)} common texts...")
    start_time = time.time()

    await cached_embedder.warmup_cache(
        texts=common_texts,
        batch_size=4,
    )

    warmup_duration = time.time() - start_time
    logger.info(f"✅ Warmup completed in {warmup_duration:.3f}s\n")

    # 现在查询这些文本（应该全部命中缓存）
    logger.info("Querying warmed-up texts...")
    start_time = time.time()

    vectors = await cached_embedder.embed_batch(common_texts)

    query_duration = time.time() - start_time
    logger.info(f"⏱️  Query duration: {query_duration:.3f}s")
    logger.info(f"🚀 Speedup: {warmup_duration / query_duration:.1f}x\n")

    # 统计
    stats = cached_embedder.get_cache_stats()
    logger.info(f"📊 Cache Stats:")
    logger.info(f"  Hit Rate: {stats['overall']['hit_rate']:.2%}")
    logger.info(f"  Total Hits: {stats['overall']['total_hits']}\n")

    await redis_client.close()


async def demo_multi_model_cache():
    """多模型缓存演示"""
    logger.info("=== Demo 5: Multi-Model Cache ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import MultiModelVectorCache
    from app.core.cached_embedder import MultiModelCachedEmbedder

    # 初始化
    redis_client = await redis.from_url("redis://localhost:6379/0")

    # 创建多个 Embedder（这里用同一个模拟不同模型）
    embedders = {
        "bge-m3": BGE_M3_Embedder(),
        "bge-m3-v2": BGE_M3_Embedder(),  # 模拟另一个模型
    }

    # 多模型缓存
    multi_model_cache = MultiModelVectorCache(
        redis_client=redis_client,
        l1_max_size_per_model=500,
        l2_ttl=3600,
    )

    # 多模型带缓存的 Embedder
    multi_cached_embedder = MultiModelCachedEmbedder(
        embedders=embedders,
        multi_model_cache=multi_model_cache,
    )

    # 测试文本
    texts = ["AI技术发展", "机器学习应用", "数据科学"]

    # 使用不同模型
    logger.info("Processing with bge-m3...")
    vectors_m3 = await multi_cached_embedder.embed_batch(texts, model="bge-m3")
    logger.info(f"  Generated {len(vectors_m3)} vectors")

    logger.info("\nProcessing with bge-m3-v2...")
    vectors_m3v2 = await multi_cached_embedder.embed_batch(texts, model="bge-m3-v2")
    logger.info(f"  Generated {len(vectors_m3v2)} vectors")

    # 再次使用 bge-m3（应该命中缓存）
    logger.info("\nProcessing with bge-m3 again (cache hit)...")
    start_time = time.time()
    vectors_m3_again = await multi_cached_embedder.embed_batch(texts, model="bge-m3")
    duration = time.time() - start_time
    logger.info(f"⏱️  Duration: {duration:.3f}s (fast!)")

    # 查看所有模型的统计
    all_stats = multi_cached_embedder.get_all_stats()
    logger.info(f"\n📊 Multi-Model Cache Stats:")

    for model, stats in all_stats.items():
        logger.info(f"\n  {model}:")
        logger.info(f"    Hit Rate: {stats['overall']['hit_rate']:.2%}")
        logger.info(f"    L1 Size: {stats['L1']['size']}")
        logger.info(f"    Compute Count: {stats['overall']['compute_count']}")

    await redis_client.close()


async def demo_performance_comparison():
    """性能对比演示"""
    logger.info("=== Demo 6: Performance Comparison ===\n")

    import redis.asyncio as redis
    from app.core.embedder import BGE_M3_Embedder
    from app.infrastructure.vector_cache import VectorCache
    from app.core.cached_embedder import CachedEmbedder

    # 初始化
    redis_client = await redis.from_url("redis://localhost:6379/0")
    base_embedder = BGE_M3_Embedder()

    vector_cache = VectorCache(
        redis_client=redis_client,
        l1_max_size=10000,
        l2_ttl=3600,
    )

    cached_embedder = CachedEmbedder(
        embedder=base_embedder,
        vector_cache=vector_cache,
        model_name="bge-m3",
    )

    # 测试数据（100个文本）
    texts = [f"测试文本 {i}" for i in range(100)]

    # 1. 无缓存性能
    logger.info("Test 1: Without cache (baseline)")
    start_time = time.time()
    await base_embedder.embed_batch(texts)
    baseline_duration = time.time() - start_time
    logger.info(f"  Duration: {baseline_duration:.3f}s")

    # 2. 首次使用缓存（未命中）
    logger.info("\nTest 2: With cache (first time, cache miss)")
    await cached_embedder.clear_cache()
    start_time = time.time()
    await cached_embedder.embed_batch(texts)
    first_cache_duration = time.time() - start_time
    logger.info(f"  Duration: {first_cache_duration:.3f}s")
    logger.info(f"  Overhead: {(first_cache_duration - baseline_duration):.3f}s")

    # 3. 第二次使用缓存（全部命中）
    logger.info("\nTest 3: With cache (second time, cache hit)")
    start_time = time.time()
    await cached_embedder.embed_batch(texts)
    second_cache_duration = time.time() - start_time
    logger.info(f"  Duration: {second_cache_duration:.3f}s")
    logger.info(f"  Speedup: {baseline_duration / second_cache_duration:.1f}x")

    # 4. 混合场景（50%命中）
    logger.info("\nTest 4: Mixed scenario (50% cache hit)")
    mixed_texts = texts[:50] + [f"新文本 {i}" for i in range(50)]
    start_time = time.time()
    await cached_embedder.embed_batch(mixed_texts)
    mixed_duration = time.time() - start_time
    logger.info(f"  Duration: {mixed_duration:.3f}s")
    logger.info(f"  Speedup: {baseline_duration / mixed_duration:.1f}x")

    # 最终统计
    stats = cached_embedder.get_cache_stats()
    logger.info(f"\n📊 Final Cache Stats:")
    logger.info(f"  Total Requests: {stats['overall']['total_requests']}")
    logger.info(f"  Total Hits: {stats['overall']['total_hits']}")
    logger.info(f"  Hit Rate: {stats['overall']['hit_rate']:.2%}")
    logger.info(f"  Cache Efficiency: {stats['overall']['cache_efficiency']:.2%}")

    # 成本节省估算
    cost_saved = (stats['overall']['total_requests'] - stats['overall']['compute_count']) / stats['overall']['total_requests']
    logger.info(f"\n💰 Cost Savings:")
    logger.info(f"  Compute Reduction: {cost_saved:.2%}")
    logger.info(f"  Estimated Token Savings: {int(cost_saved * 100)}%\n")

    await redis_client.close()


async def main():
    """运行所有演示"""
    try:
        await demo_basic_cache()
        await demo_batch_cache()
        await demo_cached_embedder()
        await demo_cache_warmup()
        await demo_multi_model_cache()
        await demo_performance_comparison()

        logger.info("✅ All demos completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
