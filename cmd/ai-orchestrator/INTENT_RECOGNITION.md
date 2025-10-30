# 意图识别优化

## 概述

AI Orchestrator 现在集成了智能意图识别功能，能够自动识别用户输入的意图类型，并路由到相应的处理管道。

## 架构设计

### 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Intent Recognition                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Rule-Based   │    │  LLM-Based   │    │   Hybrid     │ │
│  │ Recognizer   │───▶│  Recognizer  │───▶│   Strategy   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │         │
│         └────────────────────┴────────────────────┘         │
│                              ▼                               │
│                      ┌──────────────┐                       │
│                      │ Intent Cache │                       │
│                      └──────────────┘                       │
│                              ▼                               │
│         ┌────────────────────────────────────┐             │
│         │  Intent → Execution Mode Mapping   │             │
│         └────────────────────────────────────┘             │
│                              ▼                               │
│  ┌──────┐  ┌──────┐  ┌───────┐  ┌───────┐  ┌──────────┐  │
│  │ Chat │  │ RAG  │  │ Agent │  │ Voice │  │Multimodal│  │
│  └──────┘  └──────┘  └───────┘  └───────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 意图类型

| 意图类型 | 描述 | 示例 |
|---------|------|------|
| `chat` | 普通对话 | "你好", "谢谢", "再见" |
| `rag` | 知识检索问答 | "什么是AI?", "查询文档", "告诉我关于..." |
| `agent` | 任务执行 | "帮我订票", "计算结果", "发送邮件" |
| `voice` | 语音处理 | 包含音频输入的请求 |
| `multimodal` | 多模态处理 | 包含图片/视频的请求 |
| `unknown` | 未知意图 | 低置信度或无法识别的输入 |

## 功能特性

### 1. 多识别器策略

#### 基于规则的识别器
- **优先级**: 高 (Priority 1)
- **特点**: 快速、确定性、无外部依赖
- **适用场景**: 明确的关键词匹配

```go
// 示例规则
keywords: ["什么是", "怎么", "如何", "查询", "搜索"]
patterns: [
    `(?i)(what|how|why)\s+(is|are)`,
    `(?i)(查询|搜索|检索)`
]
```

#### 基于LLM的识别器
- **优先级**: 中 (Priority 2)
- **特点**: 智能、上下文感知、高准确率
- **适用场景**: 复杂语义理解

```go
// LLM提示词模板
System: "你是一个专业的意图识别系统..."
User: "用户输入 + 对话历史 + 上下文"
```

### 2. 智能缓存

```yaml
intent_recognition:
  use_cache: true
  cache_size: 10000
  cache_ttl: 600  # 秒
```

**缓存策略**:
- 仅缓存高置信度结果 (>= 0.85)
- 基于消息内容 + 租户ID的缓存键
- 自动过期清理
- 内存缓存实现（可扩展到Redis）

**缓存指标**:
```
intent_cache_hits_total
intent_cache_misses_total
intent_cache_size
```

### 3. 置信度评估

| 置信度等级 | 范围 | 处理策略 |
|-----------|------|---------|
| Very High | >= 0.95 | 直接使用 |
| High | >= 0.85 | 直接使用，缓存结果 |
| Medium | >= 0.7 | 使用，可能提示 |
| Low | >= 0.5 | 降级到默认chat模式 |
| Very Low | < 0.5 | 降级或提示用户 |

### 4. 降级策略

```go
if intent.Confidence < minConfidence {
    // 降级到普通对话模式
    intent = NewIntent(IntentTypeChat, ConfidenceMedium)
    intent.Reason = "fallback_due_to_low_confidence"
}
```

## 使用方法

### 1. 自动意图识别

```go
// 不指定mode，自动识别
request := &ChatRequest{
    Message: "什么是机器学习？",
    UserID:  "user_123",
    TenantID: "tenant_456",
    // mode 留空或设置为 "auto"
}

// 系统自动识别为 RAG 意图
// 路由到 RAG Pipeline
```

### 2. 手动指定模式

```go
// 跳过意图识别，直接使用指定模式
request := &ChatRequest{
    Message: "帮我查询天气",
    Mode:    "agent",  // 强制使用agent模式
}
```

### 3. 集成到处理管道

```go
// 构建带意图识别的处理管道
pipeline := BuildChatPipelineWithIntent(
    intentService,
    executionHandler,
)

// 责任链：
// Logging → Validation → Intent Recognition → Metrics → Execution
```

## 监控指标

### Prometheus 指标

```prometheus
# 意图识别总数
intent_recognition_total{intent_type="rag", recognizer="rule_based", tenant_id="xxx"}

# 识别耗时
intent_recognition_duration_seconds{intent_type="rag", recognizer="llm_based", tenant_id="xxx"}

# 置信度分布
intent_confidence{intent_type="agent", recognizer="rule_based", tenant_id="xxx"}

# 缓存命中率
rate(intent_cache_hits_total[5m]) /
  (rate(intent_cache_hits_total[5m]) + rate(intent_cache_misses_total[5m]))

# 低置信度识别
intent_low_confidence_total{intent_type="unknown", tenant_id="xxx"}

# 降级次数
intent_fallback_total{original_intent="rag", fallback_intent="chat", tenant_id="xxx"}

# 识别器延迟
intent_recognizer_latency_seconds{recognizer="llm_based"}

# 备选意图数量
intent_alternatives_count{intent_type="rag"}
```

### Grafana 仪表盘

建议监控面板：
1. **意图分布饼图** - 各意图类型占比
2. **识别耗时趋势** - P50/P95/P99延迟
3. **置信度分布** - 直方图
4. **缓存命中率** - 时间序列
5. **降级率** - 低置信度/降级次数趋势
6. **识别器性能对比** - 各识别器延迟对比

## 配置示例

### 完整配置

```yaml
# configs/ai-orchestrator.yaml

intent_recognition:
  enabled: true
  use_cache: true
  cache_size: 10000
  cache_ttl: 600
  min_confidence: 0.7
  use_fallback: true

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
      temperature: 0.1
```

### 环境特定配置

**开发环境** - 快速响应
```yaml
intent_recognition:
  recognizers:
    - type: rule
      enabled: true
```

**生产环境** - 高准确率
```yaml
intent_recognition:
  recognizers:
    - type: rule
      enabled: true
    - type: llm
      enabled: true
```

## API 示例

### HTTP API

```bash
# 自动意图识别
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "什么是深度学习？",
    "user_id": "user_123",
    "tenant_id": "tenant_456"
  }'

# 响应
{
  "task_id": "task_xxx",
  "events": [
    {
      "type": "intent_recognized",
      "content": "Intent: rag (confidence: 0.92)",
      "metadata": {
        "intent_type": "rag",
        "confidence": 0.92,
        "reason": "knowledge_query",
        "recognizer": "rule_based"
      }
    },
    {
      "type": "text",
      "content": "深度学习是..."
    }
  ]
}
```

### gRPC API

```protobuf
message ChatRequest {
  string message = 1;
  string user_id = 2;
  string tenant_id = 3;
  string mode = 4;  // 可选，留空则自动识别
  map<string, string> params = 5;
}

message IntentMetadata {
  string intent_type = 1;
  double confidence = 2;
  string reason = 3;
  string recognizer = 4;
  repeated AlternativeIntent alternatives = 5;
}
```

## 性能优化

### 1. 缓存优化
- 调整缓存大小和TTL
- 使用Redis分布式缓存（生产环境）
- 监控缓存命中率（目标 > 60%）

### 2. 识别器选择
- 简单场景：仅使用规则识别器
- 复杂场景：规则 + LLM混合
- 延迟敏感：优先规则，LLM作为备选

### 3. 降级策略
```go
// 超时降级
ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
defer cancel()

// LLM失败时降级到规则
if llmErr != nil {
    return ruleBasedRecognizer.Recognize(input)
}
```

## 测试

### 单元测试

```go
func TestRuleBasedRecognizer(t *testing.T) {
    recognizer := NewRuleBasedRecognizer(logger)

    input := &domain.IntentInput{
        Message: "什么是人工智能？",
    }

    intent, err := recognizer.Recognize(input)
    assert.NoError(t, err)
    assert.Equal(t, domain.IntentTypeRAG, intent.Type)
    assert.True(t, intent.IsHighConfidence())
}
```

### 集成测试

```bash
# 测试脚本
./scripts/test-intent-recognition.sh
```

## 故障排查

### 常见问题

**1. 意图识别失败**
```
检查日志: grep "intent recognition failed" logs/
原因: LLM超时、规则不匹配
解决: 启用降级策略、优化规则
```

**2. 置信度过低**
```
检查指标: intent_low_confidence_total
原因: 输入模糊、规则覆盖不足
解决: 增加规则、调整阈值、使用LLM
```

**3. 缓存命中率低**
```
检查指标: cache hit rate < 50%
原因: TTL过短、缓存容量不足
解决: 增加cache_size、延长TTL
```

## 扩展开发

### 添加自定义识别器

```go
type CustomRecognizer struct {
    // 自定义字段
}

func (r *CustomRecognizer) Recognize(input *domain.IntentInput) (*domain.Intent, error) {
    // 自定义识别逻辑
    return intent, nil
}

func (r *CustomRecognizer) Name() string {
    return "custom"
}

func (r *CustomRecognizer) Priority() int {
    return 3
}
```

### 添加新的意图类型

```go
// 在 domain/intent.go 中添加
const (
    IntentTypeCustom IntentType = "custom"
)

// 在规则识别器中添加规则
r.AddRule(&IntentRule{
    Name:       "custom_intent",
    IntentType: IntentTypeCustom,
    Keywords:   []string{"关键词"},
    Priority:   10,
})
```

## 最佳实践

1. **渐进式识别**: 先使用规则，高置信度直接返回，低置信度才调用LLM
2. **缓存策略**: 仅缓存高置信度结果，避免缓存错误
3. **降级保护**: 设置合理的置信度阈值，低置信度自动降级
4. **监控告警**: 关注低置信度比例、降级率、识别耗时
5. **A/B测试**: 对比不同识别策略的效果

## 相关文档

- [架构概览](../../docs/arch/overview.md)
- [API文档](../../api/README.md)
- [运维手册](../../docs/runbook/index.md)
- [NFR指标](../../docs/nfr/slo.md)

## 变更日志

- **2025-10-30**: 初版发布，包含规则和LLM识别器、缓存、指标
