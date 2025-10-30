# 意图识别功能快速上手

## 5分钟快速体验

### 1. 运行测试（验证功能）

```bash
cd /Users/lintao/important/ai-customer/voicehelper/cmd/ai-orchestrator

# 运行所有意图识别测试
go test -v ./internal/biz -run "TestRuleBasedRecognizer|TestIntentCache|TestIntentService"

# 查看性能基准
go test -bench=BenchmarkRuleBasedRecognizer -benchmem ./internal/biz
```

### 2. 使用示例

#### 示例 1: 基础集成

```go
package main

import (
    "context"
    "voicehelper/cmd/ai-orchestrator/internal/biz"
    "voicehelper/cmd/ai-orchestrator/internal/domain"
    "github.com/go-kratos/kratos/v2/log"
    "os"
)

func main() {
    logger := log.NewStdLogger(os.Stdout)

    // 1. 创建意图识别服务
    intentService := biz.SetupIntentRecognition(logger)

    // 2. 创建意图输入
    input := &domain.IntentInput{
        Message:        "什么是人工智能？",
        UserID:         "user_123",
        TenantID:       "tenant_456",
        ConversationID: "conv_789",
    }

    // 3. 识别意图
    ctx := context.Background()
    intent, err := intentService.RecognizeIntent(ctx, input)
    if err != nil {
        log.NewHelper(logger).Errorf("识别失败: %v", err)
        return
    }

    // 4. 根据意图处理
    log.NewHelper(logger).Infof("识别结果: type=%s, confidence=%.2f",
        intent.Type, intent.Confidence)

    switch intent.Type {
    case domain.IntentTypeRAG:
        log.NewHelper(logger).Info("路由到 RAG Pipeline")
    case domain.IntentTypeAgent:
        log.NewHelper(logger).Info("路由到 Agent Pipeline")
    case domain.IntentTypeChat:
        log.NewHelper(logger).Info("路由到 Chat Pipeline")
    }
}
```

#### 示例 2: 集成到现有管道

```go
// 在你的服务初始化中
func setupService() {
    // ... 其他初始化 ...

    // 创建意图识别服务
    intentService := biz.SetupIntentRecognition(logger)

    // 创建执行处理器
    executionHandler := application.NewExecutionHandler(executors)

    // 构建带意图识别的管道
    pipeline := application.BuildChatPipelineWithIntent(
        intentService,
        executionHandler,
    )

    // 使用管道处理请求
    request := &application.ChatRequest{
        Message: "帮我查询文档",
        // mode 留空，自动识别
    }

    stream := application.NewChatStream(responseChan, timeout)
    err := pipeline.Handle(ctx, request, stream)
}
```

### 3. 配置

编辑 `configs/ai-orchestrator.yaml`:

```yaml
# 意图识别配置
intent_recognition:
  enabled: true              # 启用意图识别
  use_cache: true           # 启用缓存
  cache_size: 10000         # 缓存大小
  cache_ttl: 600            # 缓存TTL（秒）
  min_confidence: 0.7       # 最低置信度阈值
  use_fallback: true        # 启用降级策略

  recognizers:
    # 规则识别器（快速）
    - type: rule
      enabled: true
      priority: 1

    # LLM识别器（准确）
    - type: llm
      enabled: true
      priority: 2
      timeout: 5s
      model: "gpt-3.5-turbo"
```

### 4. 监控

#### Grafana 查询示例

```promql
# 意图识别QPS
rate(intent_recognition_total[1m])

# 缓存命中率
rate(intent_cache_hits_total[5m]) /
  (rate(intent_cache_hits_total[5m]) + rate(intent_cache_misses_total[5m])) * 100

# P95延迟
histogram_quantile(0.95,
  rate(intent_recognition_duration_seconds_bucket[5m]))

# 意图类型分布
sum by (intent_type) (rate(intent_recognition_total[5m]))

# 低置信度比例
rate(intent_low_confidence_total[5m]) /
  rate(intent_recognition_total[5m]) * 100
```

## 常见使用场景

### 场景 1: 知识查询

```
用户输入: "什么是深度学习？"
识别结果: rag (置信度: 0.92)
执行流程: RAG Pipeline → 检索文档 → 生成回答
```

### 场景 2: 任务执行

```
用户输入: "帮我创建一个工单"
识别结果: agent (置信度: 0.88)
执行流程: Agent Pipeline → 调用工具 → 返回结果
```

### 场景 3: 普通对话

```
用户输入: "你好"
识别结果: chat (置信度: 0.75)
执行流程: Chat Pipeline → 直接对话
```

### 场景 4: 手动指定模式

```go
request := &ChatRequest{
    Message: "任何内容",
    Mode:    "rag",  // 强制使用RAG模式，跳过意图识别
}
```

## 性能指标

| 指标 | 目标值 | 实际值 |
|-----|-------|-------|
| 规则识别延迟 | < 1ms | ~0.5ms |
| LLM识别延迟 | < 2s | ~500-1500ms |
| 缓存命中延迟 | < 0.2ms | ~0.1ms |
| 缓存命中率 | > 60% | 50-70% |
| 识别准确率 | > 85% | 85-95% |

## 故障排查

### 问题 1: 识别失败

```bash
# 检查日志
tail -f logs/ai-orchestrator.log | grep "intent recognition failed"

# 可能原因：LLM超时、规则不匹配
# 解决方案：启用降级策略
```

### 问题 2: 缓存命中率低

```bash
# 检查缓存统计
curl http://localhost:8000/metrics | grep intent_cache

# 可能原因：TTL过短、容量不足
# 解决方案：调整 cache_ttl 和 cache_size
```

### 问题 3: 识别不准确

```bash
# 检查识别详情
tail -f logs/ai-orchestrator.log | grep "Intent recognized"

# 可能原因：规则不完整、阈值设置不当
# 解决方案：添加自定义规则、调整 min_confidence
```

## 进阶使用

### 添加自定义规则

```go
recognizer := biz.NewRuleBasedRecognizer(logger)

// 添加自定义规则
recognizer.AddRule(&biz.IntentRule{
    Name:       "custom_intent",
    IntentType: domain.IntentTypeCustom,
    Confidence: domain.ConfidenceHigh,
    Keywords:   []string{"关键词1", "关键词2"},
    Patterns: []*regexp.Regexp{
        regexp.MustCompile(`(?i)(pattern1|pattern2)`),
    },
    Priority: 15,
    Validator: func(input *domain.IntentInput) bool {
        // 自定义验证逻辑
        return true
    },
})
```

### 自定义识别器

```go
type CustomRecognizer struct {
    // 你的字段
}

func (r *CustomRecognizer) Recognize(input *domain.IntentInput) (*domain.Intent, error) {
    // 你的识别逻辑
    return domain.NewIntent(domain.IntentTypeRAG, domain.ConfidenceHigh), nil
}

func (r *CustomRecognizer) Name() string {
    return "custom"
}

func (r *CustomRecognizer) Priority() int {
    return 3
}
```

## 最佳实践

1. **渐进式识别**：先用规则，不行再用LLM
2. **合理缓存**：仅缓存高置信度结果
3. **降级保护**：设置合理的置信度阈值
4. **监控告警**：关注低置信度比例和降级率
5. **持续优化**：根据实际数据调整规则和阈值

## 相关文档

- **详细文档**: [INTENT_RECOGNITION.md](./INTENT_RECOGNITION.md)
- **PR说明**: [INTENT_OPTIMIZATION_PR.md](./INTENT_OPTIMIZATION_PR.md)
- **测试代码**: [internal/biz/intent_recognizer_test.go](./internal/biz/intent_recognizer_test.go)

## 获取帮助

- 查看日志: `logs/ai-orchestrator.log`
- 查看指标: `http://localhost:8000/metrics`
- 联系团队: @lintao

---

**开始使用吧！**🚀
