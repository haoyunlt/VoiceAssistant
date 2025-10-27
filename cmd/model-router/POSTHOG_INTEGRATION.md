# PostHog A/B Testing 集成指南

本文档介绍如何使用集成的 [PostHog](https://github.com/PostHog/posthog) 开源 A/B 测试框架进行模型路由实验。

## 📋 目录

1. [什么是 PostHog](#什么是-posthog)
2. [为什么集成 PostHog](#为什么集成-posthog)
3. [快速开始](#快速开始)
4. [功能特性](#功能特性)
5. [使用示例](#使用示例)
6. [最佳实践](#最佳实践)
7. [参考资料](#参考资料)

## 什么是 PostHog

PostHog 是一个开源的产品分析和 A/B 测试平台，提供：

- **特性标志 (Feature Flags)**: 动态开关功能
- **A/B 测试 (Experiments)**: 多变体实验
- **产品分析 (Analytics)**: 用户行为分析
- **会话回放 (Session Replay)**: 用户会话录制
- **自托管选项**: 可以部署在自己的基础设施上

GitHub: https://github.com/PostHog/posthog

## 为什么集成 PostHog

### Model Router 的 A/B 测试需求

在 AI 模型路由场景中，我们需要：

1. **模型对比测试**: GPT-4 vs Claude vs Llama
2. **策略对比测试**: 成本优化 vs 性能优先
3. **渐进式发布**: 逐步切换到新模型
4. **用户分群**: 不同用户群使用不同模型
5. **性能监控**: 延迟、成本、准确率等指标

### PostHog 的优势

- ✅ **开源免费**: MIT 许可证，可自托管
- ✅ **功能完整**: 特性标志、实验、分析一体化
- ✅ **易于集成**: 提供 Go/Python/JS 等多语言 SDK
- ✅ **实时数据**: 毫秒级数据更新
- ✅ **可视化分析**: 内置强大的数据分析和可视化工具
- ✅ **企业级**: 支持大规模部署

## 快速开始

### 1. 获取 PostHog

**选项 A: 使用云服务** (推荐快速开始)

访问 https://app.posthog.com 注册免费账户

**选项 B: 自托管部署**

```bash
# 使用 Docker Compose
git clone https://github.com/PostHog/posthog.git
cd posthog
docker-compose -f docker-compose.hobby.yml up -d
```

访问 http://localhost:8000

### 2. 配置 Model Router

编辑 `configs/posthog_config.yaml`:

```yaml
posthog:
  enabled: true
  api_key: "phc_YOUR_PROJECT_API_KEY"  # 从 PostHog 项目设置获取
  host: "https://app.posthog.com"       # 或自托管地址
```

### 3. 设置环境变量

```bash
export POSTHOG_API_KEY="phc_YOUR_PROJECT_API_KEY"
export POSTHOG_HOST="https://app.posthog.com"
export POSTHOG_ENABLED="true"
```

### 4. 启动服务

```bash
cd cmd/model-router
go run main.go
```

## 功能特性

### 1. 特性标志 (Feature Flags)

动态开关功能，无需重新部署：

```go
// 检查是否启用新模型
enabled, err := posthogService.IsFeatureEnabled(
    ctx,
    "enable_gpt4_turbo",
    userID,
    map[string]interface{}{
        "subscription": "premium",
    },
)

if enabled {
    // 使用 GPT-4 Turbo
} else {
    // 使用默认模型
}
```

### 2. 多变体实验

比较多个模型或策略：

```go
// 获取实验变体
variant, err := posthogService.GetFeatureFlagVariant(
    ctx,
    "llm_comparison_2024",
    userID,
    nil,
)

switch variant {
case "variant_a":
    modelID = "gpt-4-turbo"
case "variant_b":
    modelID = "claude-3.5-sonnet"
default:
    modelID = "gpt-3.5-turbo"  // control
}
```

### 3. 事件跟踪

记录用户行为和系统事件：

```go
// 跟踪模型选择
err := posthogService.TrackModelSelection(
    ctx,
    userID,
    experimentID,
    variantID,
    "gpt-4-turbo",
    "chat",
    map[string]interface{}{
        "prompt_tokens": 100,
        "completion_tokens": 50,
    },
)
```

### 4. 性能指标

自动收集模型性能数据：

```go
// 跟踪性能指标
metrics := &domain.ModelMetrics{
    LatencyMS:  150,
    TokensUsed: 150,
    Cost:       0.003,
    Success:    true,
}

err := posthogService.TrackModelPerformance(
    ctx,
    userID,
    experimentID,
    variantID,
    "gpt-4-turbo",
    metrics,
)
```

### 5. 用户识别

设置用户属性用于分群：

```go
// 识别用户
err := posthogService.IdentifyUser(
    ctx,
    userID,
    map[string]interface{}{
        "email":        "user@example.com",
        "subscription": "premium",
        "signup_date":  "2024-01-15",
    },
)
```

## 使用示例

### 示例 1: GPT-4 vs Claude 对比测试

```go
func (s *ModelRouterService) RouteRequest(ctx context.Context, req *Request) (*Response, error) {
    userID := req.UserID
    
    // 1. 选择实验变体
    variant, err := s.abTestService.SelectVariant(ctx, "llm_comparison_2024", userID)
    if err != nil {
        return nil, err
    }
    
    modelID := variant.ModelID  // gpt-4-turbo 或 claude-3.5-sonnet
    
    // 2. 执行推理
    startTime := time.Now()
    response, err := s.executeModel(ctx, modelID, req)
    latency := time.Since(startTime).Milliseconds()
    
    // 3. 记录结果
    success := err == nil
    s.abTestService.RecordResult(
        ctx,
        "llm_comparison_2024",
        variant.ID,
        success,
        float64(latency),
        int64(response.TokensUsed),
        response.Cost,
    )
    
    return response, err
}
```

### 示例 2: 渐进式模型发布

```go
// 逐步增加 GPT-4 的流量
// PostHog 特性标志设置:
// - 0%   -> 所有用户使用 GPT-3.5
// - 10%  -> 10% 用户试用 GPT-4
// - 50%  -> 一半用户使用 GPT-4
// - 100% -> 全面切换到 GPT-4

enabled, err := s.posthog.IsFeatureEnabled(
    ctx,
    "rollout_gpt4",
    userID,
    nil,
)

if enabled {
    return s.routeToGPT4(ctx, req)
} else {
    return s.routeToGPT35(ctx, req)
}
```

### 示例 3: 用户分群测试

```go
// 只对付费用户启用高级模型
enabled, err := s.posthog.IsFeatureEnabled(
    ctx,
    "premium_models",
    userID,
    map[string]interface{}{
        "subscription": user.Subscription,  // "free" 或 "premium"
        "usage_count":  user.UsageCount,
    },
)

if enabled && user.Subscription == "premium" {
    // 使用 GPT-4 或 Claude
    return s.routeToPremiumModel(ctx, req)
} else {
    // 使用 GPT-3.5
    return s.routeToStandardModel(ctx, req)
}
```

## 最佳实践

### 1. 实验设计

- ✅ **明确目标**: 定义要优化的指标 (延迟/成本/质量)
- ✅ **足够样本**: 每个变体至少 100 个请求
- ✅ **合理时长**: 运行 7-14 天以覆盖不同时段
- ✅ **控制变量**: 每次只测试一个变化

### 2. 性能监控

```go
// 监控关键指标
metrics := []string{
    "latency_p50",      // 中位数延迟
    "latency_p95",      // P95 延迟
    "latency_p99",      // P99 延迟
    "success_rate",     // 成功率
    "cost_per_request", // 单次请求成本
    "tokens_per_request", // 单次请求 token 数
}
```

### 3. 错误处理

```go
// 降级策略
variant, err := s.abTestService.SelectVariant(ctx, experimentID, userID)
if err != nil {
    // 实验失败时使用默认模型
    log.Warnf("A/B test failed, using default: %v", err)
    return s.routeToDefaultModel(ctx, req)
}
```

### 4. 数据隐私

```go
// 匿名化用户ID
hashedUserID := hash(userID)

// 不要发送敏感信息
properties := map[string]interface{}{
    "user_type":    "premium",
    // ❌ "email": user.Email
    // ❌ "name":  user.Name
}
```

## PostHog 控制台

### 查看实验结果

1. 登录 PostHog
2. 进入 "Experiments" 页面
3. 选择你的实验
4. 查看实时数据和统计显著性

### 分析用户行为

1. 进入 "Insights" 页面
2. 创建漏斗分析或趋势图
3. 按实验变体分组查看

### 设置告警

1. 进入 "Alerts" 页面
2. 设置指标阈值
3. 配置通知渠道 (Slack/Email)

## 架构集成

```
┌──────────────┐
│  Client API  │
└──────┬───────┘
       │
       v
┌──────────────────────┐
│  Model Router        │
│  ┌────────────────┐  │
│  │ AB Test Service│──┼───> PostHog Cloud/Self-hosted
│  │  + PostHog     │  │       - Feature Flags
│  └────────────────┘  │       - Experiments
│  │                   │       - Analytics
│  v                   │
│ ┌──────────────────┐ │
│ │ Model Selection  │ │
│ └──────────────────┘ │
└───────────┬──────────┘
            │
            v
    ┌───────────────┐
    │  LLM Models   │
    │  (GPT/Claude) │
    └───────────────┘
```

## 参考资料

### PostHog 官方文档

- [PostHog 主页](https://posthog.com)
- [Go SDK 文档](https://posthog.com/docs/libraries/go)
- [特性标志指南](https://posthog.com/docs/feature-flags)
- [实验指南](https://posthog.com/docs/experiments)
- [自托管部署](https://posthog.com/docs/self-host)

### 相关资源

- [PostHog GitHub](https://github.com/PostHog/posthog)
- [PostHog Go SDK](https://github.com/PostHog/posthog-go)
- [A/B Testing 最佳实践](https://posthog.com/blog/ab-testing-guide)

## 常见问题

### Q: PostHog 免费吗？

A: 是的，PostHog 是开源的 (MIT 许可证)，可以免费自托管。云版本提供免费额度 (100万事件/月)。

### Q: 自托管 vs 云服务？

A:
- **云服务**: 快速开始，无需运维，但数据在 PostHog 服务器
- **自托管**: 完全控制，数据私有，但需要维护基础设施

### Q: 性能影响？

A: PostHog SDK 使用批量发送和异步处理，对服务性能影响极小 (< 1ms)。

### Q: 数据保留？

A: 云版本默认保留 7 年，自托管版本可自定义。

### Q: 与现有 AB Test 框架的关系？

A: PostHog 是可选的增强功能。原有的内置 A/B 测试框架仍然可以独立使用。

## 支持

如有问题，请联系：

- GitHub Issues: https://github.com/your-org/voice-assistant/issues
- PostHog 社区: https://posthog.com/community

---

**Happy Experimenting! 🧪🚀**
