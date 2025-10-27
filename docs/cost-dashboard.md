# 成本追踪与优化看板

> **制定日期**: 2025-10-26
> **版本**: v1.0
> **目标**: Token 成本可视化、追踪与优化

---

## 📋 目录

- [成本构成](#成本构成)
- [指标采集](#指标采集)
- [Grafana 仪表盘](#grafana-仪表盘)
- [成本优化策略](#成本优化策略)
- [告警规则](#告警规则)

---

## 成本构成

### 1. AI 模型成本（最大支出）

#### Token 成本明细

| 模型           | 类型          | 单价 (USD/1K tokens) | 预计月度用量 | 月成本 (USD) |
| -------------- | ------------- | -------------------- | ------------ | ------------ |
| GPT-4          | Prompt        | $0.03                | 25M          | $750         |
| GPT-4          | Completion    | $0.06                | 25M          | $1,500       |
| GPT-3.5-Turbo  | Prompt        | $0.0005              | 100M         | $50          |
| GPT-3.5-Turbo  | Completion    | $0.0015              | 100M         | $150         |
| BGE-M3         | Embedding     | $0.0001              | 500M         | $50          |
| 通义千问-Turbo | Prompt        | ¥0.004               | 50M          | $28          |
| 通义千问-Turbo | Completion    | ¥0.008               | 50M          | $56          |
| 文心一言 4.0   | Prompt        | ¥0.008               | 25M          | $28          |
| 文心一言 4.0   | Completion    | ¥0.016               | 25M          | $56          |
| **总计**       | -             | -                    | -            | **$2,668**   |

#### 成本分解

```
对话生成: 65% ($1,734)
检索 Embedding: 2% ($50)
重排序: 5% ($134)
Agent 工具调用: 15% ($400)
其他: 13% ($350)
```

### 2. 基础设施成本

| 类型       | 月成本 (USD) | 占比 |
| ---------- | ------------ | ---- |
| 计算 (K8s) | $3,500       | 35%  |
| 数据库     | $1,200       | 12%  |
| 向量存储   | $1,500       | 15%  |
| 对象存储   | $500         | 5%   |
| 网络       | $600         | 6%   |
| 监控       | $400         | 4%   |
| AI 模型    | $2,300       | 23%  |
| **总计**   | **$10,000**  | 100% |

---

## 指标采集

### Go 服务成本追踪

**文件**: `internal/observability/cost_metrics.go`

```go
package observability

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    // Token 使用量计数器
    TokenUsageTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "token_usage_total",
            Help: "Total tokens used",
        },
        []string{
            "tenant_id",   // 租户ID
            "model",       // 模型名称
            "type",        // prompt/completion/embedding
            "service",     // 调用服务
        },
    )

    // Token 成本计数器（美元）
    TokenCostTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "token_cost_total_usd",
            Help: "Total cost in USD",
        },
        []string{
            "tenant_id",
            "model",
            "type",
            "service",
        },
    )

    // 请求成本直方图
    RequestCostHistogram = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "request_cost_usd",
            Help:    "Request cost in USD",
            Buckets: []float64{0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1, 5},
        },
        []string{"endpoint", "model"},
    )
)

// 记录 Token 使用
func RecordTokenUsage(tenantID, model, tokenType, service string, tokens int, costUSD float64) {
    TokenUsageTotal.WithLabelValues(tenantID, model, tokenType, service).Add(float64(tokens))
    TokenCostTotal.WithLabelValues(tenantID, model, tokenType, service).Add(costUSD)
}
```

### Python 服务成本追踪

**文件**: `app/core/cost_metrics.py`

```python
from prometheus_client import Counter, Histogram

# Token 使用量
token_usage_total = Counter(
    'token_usage_total',
    'Total tokens used',
    ['tenant_id', 'model', 'type', 'service']
)

# Token 成本
token_cost_total_usd = Counter(
    'token_cost_total_usd',
    'Total cost in USD',
    ['tenant_id', 'model', 'type', 'service']
)

# 请求成本
request_cost_usd = Histogram(
    'request_cost_usd',
    'Request cost in USD',
    ['endpoint', 'model'],
    buckets=[0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1, 5]
)

def record_token_usage(
    tenant_id: str,
    model: str,
    token_type: str,  # prompt/completion/embedding
    service: str,
    tokens: int,
    cost_usd: float
):
    """记录 Token 使用和成本"""
    token_usage_total.labels(
        tenant_id=tenant_id,
        model=model,
        type=token_type,
        service=service
    ).inc(tokens)
    
    token_cost_total_usd.labels(
        tenant_id=tenant_id,
        model=model,
        type=token_type,
        service=service
    ).inc(cost_usd)
```

### Model Adapter 成本计算

**文件**: `algo/model-adapter/app/services/cost_calculator.py`

```python
from typing import Dict

class CostCalculator:
    """Token 成本计算器"""
    
    # 模型价格表（USD/1K tokens）
    PRICING = {
        "gpt-4": {
            "prompt": 0.03,
            "completion": 0.06
        },
        "gpt-3.5-turbo": {
            "prompt": 0.0005,
            "completion": 0.0015
        },
        "text-embedding-ada-002": {
            "embedding": 0.0001
        },
        "bge-m3": {
            "embedding": 0.0001
        },
        "qwen-turbo": {
            "prompt": 0.0004,  # ¥0.004 / 10
            "completion": 0.0008
        },
        "ernie-bot-4": {
            "prompt": 0.0008,  # ¥0.008 / 10
            "completion": 0.0016
        }
    }
    
    @classmethod
    def calculate_cost(
        cls,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Dict[str, float]:
        """计算请求成本"""
        pricing = cls.PRICING.get(model, {})
        
        prompt_cost = prompt_tokens * pricing.get("prompt", 0) / 1000
        completion_cost = completion_tokens * pricing.get("completion", 0) / 1000
        total_cost = prompt_cost + completion_cost
        
        return {
            "prompt_cost": prompt_cost,
            "completion_cost": completion_cost,
            "total_cost": total_cost,
            "total_tokens": prompt_tokens + completion_tokens
        }
```

---

## Grafana 仪表盘

### 仪表盘配置

**文件**: `deployments/grafana/dashboards/cost-dashboard.json`

### 面板设计

#### 1. 成本概览（顶部）

**指标**:

- 今日成本
- 本月成本
- 预计月度成本
- 与预算对比

**PromQL**:

```promql
# 今日成本
sum(increase(token_cost_total_usd[24h]))

# 本月成本
sum(increase(token_cost_total_usd[30d]))

# 预计月度成本（基于当前趋势）
sum(increase(token_cost_total_usd[30d])) / day_of_month() * 30

# 预算使用率
sum(increase(token_cost_total_usd[30d])) / 2500 * 100
```

#### 2. 成本趋势（时间线）

```promql
# 按天分组的成本
sum(increase(token_cost_total_usd[1d])) by (day)

# 按小时分组的成本
sum(rate(token_cost_total_usd[1h]) * 3600)
```

#### 3. 按模型分解

```promql
# 按模型分组
sum(rate(token_cost_total_usd[5m]) * 3600 * 24 * 30) by (model)

# Top 5 最贵模型
topk(5, sum(increase(token_cost_total_usd[30d])) by (model))
```

#### 4. 按租户分解

```promql
# 按租户分组
sum(rate(token_cost_total_usd[5m]) * 3600 * 24 * 30) by (tenant_id)

# Top 10 租户
topk(10, sum(increase(token_cost_total_usd[30d])) by (tenant_id))
```

#### 5. 按服务分解

```promql
# 按服务分组
sum(rate(token_cost_total_usd[5m]) * 3600 * 24 * 30) by (service)

# 饼图
sum(increase(token_cost_total_usd[30d])) by (service)
```

#### 6. Token 使用统计

```promql
# 总 Token 数
sum(rate(token_usage_total[5m]) * 3600 * 24 * 30)

# 按类型分组（prompt vs completion）
sum(rate(token_usage_total[5m]) * 3600 * 24 * 30) by (type)

# Prompt/Completion 比例
sum(rate(token_usage_total{type="prompt"}[5m])) /
sum(rate(token_usage_total{type="completion"}[5m]))
```

#### 7. 单请求成本分布

```promql
# P50/P90/P99 请求成本
histogram_quantile(0.50, sum(rate(request_cost_usd_bucket[5m])) by (le))
histogram_quantile(0.90, sum(rate(request_cost_usd_bucket[5m])) by (le))
histogram_quantile(0.99, sum(rate(request_cost_usd_bucket[5m])) by (le))
```

#### 8. 成本异常检测

```promql
# 成本增长率（与昨天对比）
(
  sum(increase(token_cost_total_usd[1d]))
  -
  sum(increase(token_cost_total_usd[1d] offset 1d))
)
/
sum(increase(token_cost_total_usd[1d] offset 1d)) * 100

# 成本异常（超过 3σ）
abs(
  sum(rate(token_cost_total_usd[5m]))
  -
  avg_over_time(sum(rate(token_cost_total_usd[5m]))[1h:5m])
)
>
3 * stddev_over_time(sum(rate(token_cost_total_usd[5m]))[1h:5m])
```

---

## 成本优化策略

### 1. 分级服务策略

#### 租户分级

| 级别     | 描述         | 模型策略           | 上下文长度 | 预计成本/用户 |
| -------- | ------------ | ------------------ | ---------- | ------------- |
| **金牌** | 企业客户     | GPT-4 优先         | 16K        | $50/月        |
| **银牌** | 专业用户     | GPT-3.5-Turbo 主力 | 8K         | $20/月        |
| **铜牌** | 免费/试用    | 国产模型为主       | 4K         | $5/月         |
| **API**  | API 调用客户 | 按需选择           | 可配置     | 按量计费      |

#### 实现

**文件**: `internal/biz/cost_tier.go`

```go
type CostTier string

const (
    TierGold   CostTier = "gold"
    TierSilver CostTier = "silver"
    TierBronze CostTier = "bronze"
    TierAPI    CostTier = "api"
)

type TierConfig struct {
    Tier           CostTier
    PrimaryModel   string
    FallbackModel  string
    MaxContextLen  int
    DailyCostLimit float64
}

var TierConfigs = map[CostTier]TierConfig{
    TierGold: {
        Tier:           TierGold,
        PrimaryModel:   "gpt-4",
        FallbackModel:  "gpt-3.5-turbo",
        MaxContextLen:  16384,
        DailyCostLimit: 2.0, // $2/day
    },
    TierSilver: {
        Tier:           TierSilver,
        PrimaryModel:   "gpt-3.5-turbo",
        FallbackModel:  "qwen-turbo",
        MaxContextLen:  8192,
        DailyCostLimit: 0.8, // $0.8/day
    },
    TierBronze: {
        Tier:           TierBronze,
        PrimaryModel:   "qwen-turbo",
        FallbackModel:  "ernie-bot-4",
        MaxContextLen:  4096,
        DailyCostLimit: 0.2, // $0.2/day
    },
}
```

### 2. 缓存策略

#### 语义缓存

**原理**: 使用向量相似度匹配相似查询

**实现**: `pkg/cache/semantic_cache.go`

```go
type SemanticCache struct {
    redis    *redis.Client
    milvus   *milvus.Client
    ttl      time.Duration
    threshold float64 // 相似度阈值
}

func (c *SemanticCache) Get(query string) (*CachedResponse, error) {
    // 1. 向量化查询
    embedding := c.embedQuery(query)
    
    // 2. Milvus 相似度搜索
    similar := c.milvus.Search(embedding, topK=1)
    
    // 3. 如果相似度 > 阈值，返回缓存结果
    if similar.Score > c.threshold {
        return c.redis.Get(similar.ID)
    }
    
    return nil, ErrCacheMiss
}
```

**效果**:

- 缓存命中率: 30-50%
- 成本节省: 30-50%

#### 完全匹配缓存

**适用**: 相同查询（FAQ、常见问题）

```go
func (c *ExactCache) Get(query string) (*CachedResponse, error) {
    key := "cache:exact:" + md5(query)
    return c.redis.Get(key)
}
```

**TTL**:

- FAQ: 7 天
- 一般对话: 24 小时
- 实时数据: 无缓存

### 3. 上下文压缩

#### 策略

| 方法         | 压缩率 | 质量损失 | 适用场景     |
| ------------ | ------ | -------- | ------------ |
| 截断最老消息 | 50%    | 低       | 长对话       |
| 总结历史     | 70%    | 中       | 超长对话     |
| 保留关键信息 | 60%    | 低       | 专业对话     |
| 重要性排序   | 40%    | 极低     | 检索结果压缩 |

#### 实现

```python
class ContextCompressor:
    """上下文压缩器"""
    
    def compress(self, messages: List[Message], target_tokens: int) -> List[Message]:
        """压缩到目标 Token 数"""
        current_tokens = self.count_tokens(messages)
        
        if current_tokens <= target_tokens:
            return messages
        
        # 策略1: 保留系统消息 + 最近N条
        system_msgs = [m for m in messages if m.role == "system"]
        recent_msgs = messages[-10:]
        
        compressed = system_msgs + recent_msgs
        compressed_tokens = self.count_tokens(compressed)
        
        # 策略2: 如果还是太长，总结中间部分
        if compressed_tokens > target_tokens:
            summary = self.summarize(messages[len(system_msgs):-10])
            compressed = system_msgs + [summary] + recent_msgs
        
        return compressed
```

### 4. 模型自动降级

#### 触发条件

- 成本超限（日度/月度预算）
- 延迟过高（SLO 违约）
- 模型服务不可用

#### 降级链

```
GPT-4 → GPT-3.5-Turbo → Qwen-Turbo → Ernie-Bot → 拒绝服务
```

#### 实现

```go
func (s *ModelService) SelectModel(tier CostTier, currentCost float64) string {
    config := TierConfigs[tier]
    
    // 检查成本限制
    if currentCost > config.DailyCostLimit * 0.9 {
        // 接近限制，使用备用模型
        return config.FallbackModel
    }
    
    // 检查主模型可用性
    if !s.isModelAvailable(config.PrimaryModel) {
        return config.FallbackModel
    }
    
    return config.PrimaryModel
}
```

---

## 告警规则

### Prometheus 告警

**文件**: `configs/monitoring/cost-alerts.yml`

```yaml
groups:
  - name: cost_alerts
    interval: 5m
    rules:
      # 日度成本超限
      - alert: DailyCostHigh
        expr: |
          sum(increase(token_cost_total_usd[24h])) > 200
        labels:
          severity: warning
        annotations:
          summary: "日度成本超过 $200"
          description: "当前: ${{ $value }}"

      # 成本增长异常
      - alert: CostSpike
        expr: |
          (
            sum(rate(token_cost_total_usd[5m]))
            /
            avg_over_time(sum(rate(token_cost_total_usd[5m]))[1h:5m])
          ) > 3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "成本突增 3 倍"

      # 单租户成本异常
      - alert: TenantCostHigh
        expr: |
          sum(increase(token_cost_total_usd[1d])) by (tenant_id) > 50
        labels:
          severity: warning
        annotations:
          summary: "租户 {{ $labels.tenant_id }} 日成本超过 $50"

      # 月度预算告警（80%）
      - alert: MonthlyBudget80Percent
        expr: |
          sum(increase(token_cost_total_usd[30d])) > 2000
        labels:
          severity: warning
        annotations:
          summary: "月度成本达到预算的 80%"

      # 月度预算告警（100%）
      - alert: MonthlyBudgetExceeded
        expr: |
          sum(increase(token_cost_total_usd[30d])) > 2500
        labels:
          severity: critical
        annotations:
          summary: "月度成本超过预算"
```

---

## 成本报表

### 月度成本报表

**生成时间**: 每月 1 号 8:00

**内容**:

1. **成本总览**

   - 总成本与预算对比
   - 同比/环比增长
   - Top 10 成本项

2. **按维度分解**

   - 按模型
   - 按租户
   - 按服务
   - 按Token 类型

3. **优化建议**

   - 高成本租户识别
   - 低效查询识别
   - 缓存命中率分析
   - 模型选择优化

4. **趋势预测**
   - 下月预计成本
   - 增长趋势
   - 风险提示

---

## 参考资料

- [NFR 基线](nfr-baseline.md)
- [OpenAI Pricing](https://openai.com/pricing)
- [Prometheus 最佳实践](https://prometheus.io/docs/practices/)

---

**制定人**: SRE + FinOps Team
**审批**: CTO + CFO
**生效日期**: 2025-10-27
**下次审查**: 每月

---

**💡 优化原则**:

- **测量**: 精确追踪每一分钱
- **分析**: 找出成本热点
- **优化**: 持续改进策略
- **平衡**: 成本与质量的最佳平衡


