# A/B测试集成架构文档

## 概述

Model Router 服务现已集成完整的 A/B 测试功能，支持在生产环境中对不同 LLM 模型进行对比测试，帮助团队做出数据驱动的模型选择决策。

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP API Layer                        │
│              (abtest_handler.go)                         │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│                 Service Layer                            │
│          (model_router_service.go)                       │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│              Application Layer                           │
│  ┌────────────────────┐    ┌──────────────────────┐    │
│  │ ABTestingServiceV2 │    │  RoutingService      │    │
│  │  - SelectVariant   │◄───│  - routeWithABTest   │    │
│  │  - RecordMetric    │    │  - Route             │    │
│  └────────────────────┘    └──────────────────────┘    │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│               Domain Layer                               │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ ABTestConfig │  │  ABVariant  │  │ ABTestMetric  │  │
│  └──────────────┘  └─────────────┘  └───────────────┘  │
└───────────────────┬─────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────┐
│         Infrastructure & Data Layer                      │
│  ┌──────────────────┐         ┌──────────────────────┐  │
│  │  ABTestCache     │         │   ABTestRepository   │  │
│  │  (Redis)         │         │   (PostgreSQL)       │  │
│  └──────────────────┘         └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. Domain Layer (领域层)

**ABTestConfig** - A/B测试配置
- 测试ID、名称、描述
- 时间范围（开始/结束）
- 状态（draft/running/paused/completed）
- 分流策略（consistent_hash/weighted_random）
- 变体列表

**ABVariant** - 测试变体
- 变体ID、名称
- 关联的模型ID
- 流量权重（0-1）

**ABTestMetric** - 测试指标
- 请求记录（成功/失败）
- 延迟、Token用量、成本

#### 2. Application Layer (应用层)

**ABTestingServiceV2** - A/B测试核心服务
```go
// 核心方法
SelectVariant(ctx, testID, userID) -> *ABVariant
RecordResult(ctx, testID, variantID, userID, metrics)
CreateTest(ctx, req) -> *ABTestConfig
StartTest/PauseTest/CompleteTest(ctx, testID)
```

**RoutingService** - 增强的路由服务
```go
// 集成A/B测试的路由
Route(ctx, req) -> *RoutingResponse {
    if req.EnableABTest && req.UserID != "" {
        return routeWithABTest(ctx, req)
    }
    // 常规路由逻辑
}
```

#### 3. Infrastructure Layer (基础设施层)

**ABTestCache** - Redis缓存实现
- 测试配置缓存 (TTL: 1小时)
- 用户变体分配缓存 (TTL: 24小时)
- 缓存失效管理

**ABTestRepository** - PostgreSQL持久化
- CRUD操作
- 指标记录
- 聚合查询（物化视图）

## 关键流程

### 1. 创建A/B测试

```bash
POST /api/v1/abtests
{
  "name": "GPT-4 vs Claude-3",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-08T00:00:00Z",
  "strategy": "consistent_hash",
  "variants": [
    {"id": "v1", "model_id": "gpt-4-turbo-preview", "weight": 0.5},
    {"id": "v2", "model_id": "claude-3-opus-20240229", "weight": 0.5}
  ]
}
```

**流程**:
1. 验证变体配置（权重总和=1.0，模型存在）
2. 创建测试记录（状态: draft）
3. 返回测试ID

### 2. 启动测试

```bash
POST /api/v1/abtests/{test_id}/start
```

**流程**:
1. 验证测试状态和时间范围
2. 更新状态为 `running`
3. 缓存测试配置到Redis

### 3. 路由请求（带A/B测试）

```bash
POST /api/v1/route
{
  "prompt": "用户问题",
  "max_tokens": 1000,
  "strategy": "cheapest",
  "user_id": "user123",
  "enable_ab_test": true
}
```

**流程**:
1. **检查A/B测试**: `enable_ab_test=true` 且 `user_id` 存在
2. **查找活跃测试**: 自动查找 `status=running` 的测试
3. **选择变体**:
   - 检查Redis缓存: `abtest:user_variant:{test_id}:{user_id}`
   - 缓存命中: 直接返回已分配的变体
   - 缓存未命中:
     - 获取测试配置
     - 应用分流策略（consistent_hash 或 weighted_random）
     - 缓存用户变体分配
4. **获取模型**: 根据变体的 `model_id` 获取模型信息
5. **返回响应**: 包含 `ab_test_id` 和 `variant_id`

### 4. 记录指标

**自动记录**（在 `RecordUsage` 中）:
```go
if response.IsABTest {
    abTestService.RecordResult(
        ctx,
        response.ABTestID,
        response.VariantID,
        userID,
        success,
        latencyMs,
        tokens,
        cost,
    )
}
```

**手动记录**:
```bash
POST /api/v1/abtests/{test_id}/metrics
{
  "variant_id": "v1",
  "user_id": "user123",
  "success": true,
  "latency_ms": 450.5,
  "tokens": 500,
  "cost": 0.015
}
```

### 5. 查看结果

```bash
GET /api/v1/abtests/{test_id}/results
```

**返回**:
```json
{
  "test_id": "test_001",
  "results": {
    "v1": {
      "request_count": 1000,
      "success_count": 995,
      "avg_latency_ms": 450.5,
      "total_cost": 15.75
    },
    "v2": {
      "request_count": 1000,
      "success_count": 998,
      "avg_latency_ms": 380.2,
      "total_cost": 18.20
    }
  }
}
```

## 分流策略

### 1. 一致性哈希 (consistent_hash)

**适用场景**: 需要用户体验一致性

**实现原理**:
```go
hash := crc32.ChecksumIEEE([]byte(testID + userID))
normalizedHash := float64(hash) / float64(math.MaxUint32)

// 加权选择
cumulative := 0.0
for _, variant := range variants {
    cumulative += variant.Weight
    if normalizedHash < cumulative {
        return variant
    }
}
```

**特性**:
- 同一用户在测试期间始终分配到相同变体
- 分布均匀，符合权重比例
- 支持动态调整权重（重启后生效）

### 2. 加权随机 (weighted_random)

**适用场景**: 快速探索和实验

**实现原理**:
```go
rand.Seed(time.Now().UnixNano())
r := rand.Float64()

cumulative := 0.0
for _, variant := range variants {
    cumulative += variant.Weight
    if r < cumulative {
        return variant
    }
}
```

**特性**:
- 每次请求独立随机选择
- 符合权重比例的概率分布
- 适合快速验证假设

## 数据模型

### PostgreSQL Schema

```sql
-- A/B测试配置表
CREATE TABLE model_router.ab_tests (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    variants JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    created_by VARCHAR(64)
);

-- A/B测试指标表
CREATE TABLE model_router.ab_test_metrics (
    id UUID PRIMARY KEY,
    test_id VARCHAR(64) NOT NULL,
    variant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    success BOOLEAN NOT NULL,
    latency_ms FLOAT,
    tokens_used BIGINT,
    cost_usd FLOAT,
    model_id VARCHAR(100),
    metadata JSONB
);

-- 聚合结果物化视图
CREATE MATERIALIZED VIEW model_router.ab_test_results AS
SELECT
    test_id,
    variant_id,
    COUNT(*) AS request_count,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) AS success_count,
    AVG(latency_ms) AS avg_latency_ms,
    SUM(tokens_used) AS total_tokens,
    SUM(cost_usd) AS total_cost
FROM model_router.ab_test_metrics
GROUP BY test_id, variant_id;
```

### Redis 缓存结构

```
# 测试配置缓存
Key: abtest:test:{test_id}
Value: JSON(ABTestConfig)
TTL: 1 hour

# 用户变体分配缓存
Key: abtest:user_variant:{test_id}:{user_id}
Value: JSON(ABVariant)
TTL: 24 hours
```

## 配置示例

### configs/model-router.yaml

```yaml
abtest:
  enabled: true
  cache_ttl: 1h
  user_variant_cache_ttl: 24h
  default_strategy: consistent_hash

redis:
  addr: localhost:6379
  db: 0
  pool_size: 100

database:
  driver: postgres
  host: localhost
  port: 5432
  database: voiceassistant
```

## 最佳实践

### 1. 测试设计

✅ **推荐**:
- 样本量 ≥ 1000 次请求/变体
- 测试时长 ≥ 7 天
- 2-3 个变体
- 保守权重分配（如 90%/10%）

❌ **避免**:
- 样本量过小导致结论不可靠
- 测试时间过短无法覆盖周期性变化
- 过多变体导致分流不足

### 2. 分流策略选择

| 场景 | 推荐策略 | 原因 |
|------|---------|------|
| 生产A/B测试 | consistent_hash | 用户体验一致性 |
| 快速验证 | weighted_random | 快速收集数据 |
| 长期对比 | consistent_hash | 减少混杂因素 |
| 灰度发布 | consistent_hash | 逐步放量 |

### 3. 监控指标

**核心指标**:
- 成功率: `success_count / request_count`
- P50/P95/P99延迟
- 成本效率: `total_cost / total_tokens`
- 用户满意度（需外部收集）

**统计检验**:
- t检验: 比较平均延迟差异
- 卡方检验: 比较成功率差异
- 置信区间: 95% CI

### 4. 缓存策略

✅ **推荐**:
- 测试配置缓存: 1小时（平衡性能和一致性）
- 用户变体缓存: 24小时（确保用户体验一致）
- 测试结束后立即清除缓存

❌ **避免**:
- 缓存TTL过长导致配置更新不及时
- 缓存TTL过短增加数据库压力

## 运维指南

### 部署检查清单

- [ ] 数据库迁移已应用
- [ ] Redis连接正常
- [ ] 配置文件正确
- [ ] Wire依赖注入已生成
- [ ] 健康检查通过
- [ ] 监控仪表盘配置完成

### 故障排查

**问题**: 用户未被分配到变体

**排查步骤**:
1. 检查测试状态: `GET /api/v1/abtests`
2. 验证时间范围: `start_time < now < end_time`
3. 检查Redis连接: `redis-cli ping`
4. 查看日志: `grep "ab test" /var/log/model-router.log`

**问题**: 指标未记录

**排查步骤**:
1. 验证数据库连接
2. 检查外键约束: `test_id` 必须存在
3. 查看错误日志

### 性能优化

**数据库优化**:
- 定期刷新物化视图: `REFRESH MATERIALIZED VIEW model_router.ab_test_results`
- 归档历史数据: 保留最近30天
- 使用连接池: `max_open_conns: 100`

**Redis优化**:
- 使用pipeline批量操作
- 监控内存使用: `redis-cli info memory`
- 配置合理的驱逐策略: `maxmemory-policy allkeys-lru`

## 扩展规划

### 短期 (1-3 months)
- [ ] ClickHouse集成（高性能指标存储）
- [ ] 多臂老虎机算法（动态调整权重）
- [ ] PostHog集成（用户行为分析）
- [ ] Grafana Dashboard模板

### 中期 (3-6 months)
- [ ] 多因子实验（同时测试多个因素）
- [ ] 自动化决策（基于统计显著性）
- [ ] 成本预算告警
- [ ] 实时流式聚合

### 长期 (6-12 months)
- [ ] 因果推断分析
- [ ] 推荐模型（自动推荐最佳模型）
- [ ] 跨租户A/B测试
- [ ] ML特征工程集成

## 参考资料

- [领域驱动设计 (DDD)](https://github.com/go-kratos/kratos)
- [一致性哈希算法](https://en.wikipedia.org/wiki/Consistent_hashing)
- [A/B测试最佳实践](https://www.optimizely.com/optimization-glossary/ab-testing/)
- [统计显著性检验](https://www.statsig.com/blog/statistical-significance)

## 联系方式

技术支持: dev@voiceassistant.ai
文档贡献: [GitHub Issues](https://github.com/voiceassistant/issues)
