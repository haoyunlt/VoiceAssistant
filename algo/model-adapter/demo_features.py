"""演示新功能的脚本."""

import asyncio


async def demo_resilience():
    """演示重试和熔断功能."""
    print("\n" + "=" * 60)
    print("🔥 Demo 1: 重试和熔断器")
    print("=" * 60)

    from app.core.resilience import get_circuit_breaker, with_resilience

    # 模拟可能失败的API调用
    call_count = 0

    @with_resilience("demo_provider", max_attempts=3, timeout=2.0)
    async def flaky_api_call():
        nonlocal call_count
        call_count += 1
        print(f"  🔄 尝试 #{call_count}...")

        if call_count < 2:
            raise Exception("模拟API失败")

        return {"result": "success"}

    try:
        result = await flaky_api_call()
        print(f"  ✅ 成功: {result}")
    except Exception as e:
        print(f"  ❌ 失败: {e}")

    # 查看熔断器状态
    breaker = get_circuit_breaker("demo_provider")
    print(f"  📊 熔断器状态: {breaker.current_state}")


async def demo_cache():
    """演示缓存功能."""
    print("\n" + "=" * 60)
    print("⚡ Demo 2: 语义缓存")
    print("=" * 60)

    from app.core.cache import SemanticCache

    cache = SemanticCache(
        redis_url="redis://localhost:6379/0",
        default_ttl=120,
        enabled=True,
    )

    await cache.connect()

    messages = [{"role": "user", "content": "Hello, how are you?"}]

    # 第一次请求 - 缓存未命中
    cached = await cache.get("openai", "gpt-3.5-turbo", messages)
    print(f"  🔍 第一次查询: {'命中' if cached else '未命中'} ❌")

    # 设置缓存
    await cache.set(
        "openai",
        "gpt-3.5-turbo",
        messages,
        {"content": "I'm doing great!", "usage": {"total_tokens": 20}},
    )
    print("  💾 已缓存响应")

    # 第二次请求 - 缓存命中
    cached = await cache.get("openai", "gpt-3.5-turbo", messages)
    print(f"  🔍 第二次查询: {'命中' if cached else '未命中'} ✅")

    if cached:
        print(f"  📄 缓存内容: {cached['content']}")

    # 统计信息
    stats = await cache.get_stats()
    print(f"  📊 缓存统计: {stats}")

    await cache.close()


def demo_token_counter():
    """演示Token计数."""
    print("\n" + "=" * 60)
    print("🔢 Demo 3: Token计数 (tiktoken)")
    print("=" * 60)

    from app.core.token_counter import CostCalculator, TokenCounter

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "请用中文介绍一下人工智能的发展历史。"},
    ]

    # Token计数
    tokens = TokenCounter.count_message_tokens(messages, model="gpt-4")
    print(f"  📊 总Token数: {tokens}")

    # 成本计算
    cost = CostCalculator.calculate_cost(
        model="gpt-4",
        input_tokens=tokens,
        output_tokens=500,
    )

    print(f"  💰 输入成本: ${cost['input_cost']:.6f}")
    print(f"  💰 输出成本: ${cost['output_cost']:.6f}")
    print(f"  💰 总成本: ${cost['total_cost']:.6f}")

    # 模型对比
    models = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o"]
    comparison = CostCalculator.compare_model_costs(models, tokens, 500)

    print("\n  📊 模型成本对比:")
    for model, cost_data in comparison.items():
        print(f"    {model:20s}: ${cost_data['total_cost']:.6f}")

    # 最便宜的模型
    cheapest_model, cheapest_cost = CostCalculator.get_cheapest_model(models, tokens, 500)
    print(f"\n  🏆 最便宜: {cheapest_model} (${cheapest_cost['total_cost']:.6f})")


def demo_smart_router():
    """演示智能路由."""
    print("\n" + "=" * 60)
    print("🎯 Demo 4: 智能路由")
    print("=" * 60)

    from app.core.smart_router import SmartRouter

    router = SmartRouter()

    messages = [{"role": "user", "content": "What is 2+2?"}]

    # 低质量要求 - 应该选择便宜模型
    result = router.route(
        quality_level="low",
        messages=messages,
        available_providers=["openai", "zhipu"],
    )

    print("  📍 质量要求: low")
    print(f"  ✅ 选择模型: {result.provider}/{result.model}")
    print(f"  💰 预估成本: ${result.estimated_cost:.6f}")

    # 高质量要求 - 应该选择高性能模型
    result = router.route(
        quality_level="high",
        messages=messages,
        available_providers=["openai", "claude"],
    )

    print("\n  📍 质量要求: high")
    print(f"  ✅ 选择模型: {result.provider}/{result.model}")
    print(f"  💰 预估成本: ${result.estimated_cost:.6f}")

    # 预算路由
    result = router.route_with_budget(
        messages=messages,
        budget_usd=0.01,
        available_providers=["openai"],
    )

    print("\n  💵 预算限制: $0.01")
    print(f"  ✅ 选择模型: {result.provider}/{result.model}")
    print(f"  💰 预估成本: ${result.estimated_cost:.6f}")


def demo_budget_manager():
    """演示预算管理."""
    print("\n" + "=" * 60)
    print("💵 Demo 5: 预算管理")
    print("=" * 60)

    from app.core.budget_manager import get_budget_manager

    manager = get_budget_manager()

    # 设置预算
    manager.set_budget(
        tenant_id="demo_tenant",
        daily_limit_usd=100.0,
        warning_threshold=0.8,
        auto_downgrade=True,
    )
    print("  ⚙️  已设置预算: $100/天, 警告阈值80%")

    # 模拟使用
    print("\n  📊 模拟使用:")
    for i in range(5):
        usage = 18.5
        manager.record_usage("demo_tenant", usage)
        status = manager.get_status("demo_tenant")

        emoji = "🟢" if status.usage_percent < 0.8 else "🟡" if status.usage_percent < 1.0 else "🔴"
        print(
            f"    第{i + 1}次: +${usage:.2f} → ${status.current_usage_usd:.2f} / ${status.daily_limit_usd:.2f} ({status.usage_percent * 100:.1f}%) {emoji}"
        )

        if status.is_exceeded:
            print(f"      ⚠️  超预算! 自动降级: {status.auto_downgraded}")
            break

    # 检查是否应降级
    should_downgrade, quality = manager.should_downgrade("demo_tenant")
    if should_downgrade:
        print(f"\n  ⬇️  应降级到: {quality}")


def demo_metrics():
    """演示指标收集."""
    print("\n" + "=" * 60)
    print("📊 Demo 6: Prometheus指标")
    print("=" * 60)

    from app.core.metrics import MetricsRecorder

    # 记录一次请求
    MetricsRecorder.record_request(
        provider="openai",
        model="gpt-4",
        duration_seconds=1.23,
        input_tokens=1234,
        output_tokens=567,
        cost_usd=0.071,
        success=True,
    )
    print("  ✅ 已记录请求指标")

    # 记录缓存
    MetricsRecorder.record_cache_hit("openai", "gpt-4")
    MetricsRecorder.record_cache_miss("openai", "gpt-4")
    print("  ✅ 已记录缓存指标")

    # 更新熔断器状态
    MetricsRecorder.update_circuit_breaker_state("openai", "closed")
    print("  ✅ 已更新熔断器指标")

    print("\n  📍 访问指标: http://localhost:8005/metrics")
    print("  📍 关键指标:")
    print("    - model_request_duration_seconds (P50/P95/P99)")
    print("    - cache_hit_rate")
    print("    - circuit_breaker_state")
    print("    - cost_usd_total")


async def main():
    """主函数."""
    print("\n" + "=" * 80)
    print(" 🚀 Model Adapter 增强功能演示")
    print("=" * 80)

    await demo_resilience()
    await demo_cache()
    demo_token_counter()
    demo_smart_router()
    demo_budget_manager()
    demo_metrics()

    print("\n" + "=" * 80)
    print(" ✅ 演示完成!")
    print("=" * 80)
    print("\n📚 更多信息:")
    print("  - 实现总结: IMPLEMENTATION_SUMMARY.md")
    print("  - 完整文档: OPTIMIZATION.md")
    print("  - API文档: http://localhost:8005/docs")
    print("  - 指标: http://localhost:8005/metrics")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
