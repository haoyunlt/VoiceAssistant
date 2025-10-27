# Analytics Service

分析服务 - 实时统计、数据分析、报表生成

## 功能特性

### 1. 实时统计

- 活跃用户数
- 当前对话数
- 每分钟消息数
- AI 请求速率
- 平均响应时间

### 2. 用户分析

- 用户活跃度
- 用户留存率
- 用户参与度
- 功能使用统计
- Cohort 分析

### 3. 对话分析

- 对话统计（按模式）
- 对话趋势
- 平均消息数
- 平均时长
- 成功率

### 4. 文档分析

- 上传统计
- 索引状态
- 格式分布
- 检索频率
- 热门文档

### 5. AI 使用分析

- 请求统计（按类型）
- Token 使用量
- 成本分析
- 性能指标
- 模型对比

### 6. 租户分析

- 租户排名
- 配额使用
- 成本分配
- 活跃度对比

### 7. 报表生成

- 周报 / 月报
- 自定义报表
- PDF / Excel 导出
- 定时生成
- 邮件发送

## API 接口

### GET /api/v1/stats/realtime

获取实时统计

**响应**:

```json
{
  "timestamp": "2025-10-26T10:30:00Z",
  "active_users": 125,
  "active_conversations": 45,
  "messages_per_minute": 230,
  "ai_requests_per_minute": 85,
  "avg_response_time_ms": 450
}
```

### GET /api/v1/stats/summary?period=today

获取统计摘要

**响应**:

```json
{
  "period": "today",
  "users": {
    "total_active": 1250,
    "new_users": 45,
    "returning_users": 1205
  },
  "conversations": {
    "total": 3500,
    "avg_messages": 12.5,
    "avg_duration_minutes": 8.2
  },
  "documents": {
    "total_uploaded": 280,
    "total_indexed": 275,
    "total_retrieved": 8500
  },
  "ai": {
    "total_requests": 12000,
    "total_tokens": 4500000,
    "total_cost_usd": 125.5
  }
}
```

### GET /api/v1/users/activity

获取用户活跃度

### GET /api/v1/ai/cost

获取 AI 成本分析

**响应**:

```json
{
  "total_cost_usd": 125.5,
  "total_tokens": 4500000,
  "by_model": [
    {
      "model": "gpt-4-turbo-preview",
      "tokens": 2000000,
      "cost_usd": 80.0
    },
    {
      "model": "gpt-3.5-turbo",
      "tokens": 2500000,
      "cost_usd": 45.5
    }
  ],
  "avg_cost_per_request_usd": 0.0105
}
```

### POST /api/v1/reports/generate

生成报表

**请求**:

```json
{
  "type": "monthly_summary",
  "tenant_id": "tenant_123",
  "start_date": "2025-10-01",
  "end_date": "2025-10-31",
  "format": "pdf",
  "email_to": "admin@example.com"
}
```

## 数据源

### ClickHouse 表

```sql
-- 消息统计表（来自 Flink）
message_stats_minute
message_stats_hourly
message_stats_daily

-- 用户活跃度表
user_activity_hourly
user_activity_daily

-- AI 使用统计
ai_usage_hourly
ai_cost_daily

-- 文档统计
document_stats_daily
document_retrieval_stats
```

### 实时数据

- Redis 缓存（最近 5 分钟数据）
- 直接查询 PostgreSQL（当前状态）

## 配置

```yaml
analytics:
  clickhouse:
    host: clickhouse:9000
    database: voiceassistant
    username: default
    password: ${CLICKHOUSE_PASSWORD}
    connection_pool_size: 10

  cache:
    redis_url: redis://redis:6379/5
    ttl: 5m

  realtime:
    update_interval: 10s
    aggregation_window: 5m

  reports:
    storage_path: /app/reports
    retention_days: 90
    max_concurrent_jobs: 3

    templates:
      - type: daily_summary
        schedule: '0 0 * * *' # 每天 00:00
      - type: weekly_summary
        schedule: '0 0 * * 0' # 每周日 00:00
      - type: monthly_summary
        schedule: '0 0 1 * *' # 每月 1 号 00:00
```

## 性能优化

### 1. 数据聚合

- 使用 ClickHouse 物化视图
- 预聚合常用指标
- 分级聚合（分钟 → 小时 → 天）

### 2. 缓存策略

- Redis 缓存实时数据
- 本地缓存静态配置
- CDN 缓存报表文件

### 3. 查询优化

- 索引优化
- 分区裁剪
- 并行查询
- 结果缓存

## 部署

### Docker

```bash
docker build -t analytics-service:latest .
docker run -p 9006:9006 analytics-service:latest
```

### Kubernetes

```bash
kubectl apply -f deployments/k8s/analytics-service.yaml
```

## 监控

Prometheus 指标暴露在 `/metrics`：

- `analytics_queries_total` - 总查询数
- `analytics_query_duration_seconds` - 查询延迟
- `analytics_cache_hit_rate` - 缓存命中率
- `analytics_report_generation_duration_seconds` - 报表生成时间

## 开发

### 编译

```bash
go build -o analytics-service ./cmd/analytics-service
```

### 运行

```bash
./analytics-service
```

### 测试

```bash
go test ./...
```
