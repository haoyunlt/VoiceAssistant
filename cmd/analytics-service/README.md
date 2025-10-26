# Analytics Service

分析服务 - 提供实时统计和报表生成功能。

## 🎯 核心功能

- **实时统计**: 使用统计、模型统计、用户行为、成本分解
- **报表生成**: 异步生成各类报表（使用报表、成本报表、模型报表、用户报表）
- **ClickHouse 集成**: 高性能 OLAP 查询
- **多租户支持**: 租户级别数据隔离

## 📋 技术栈

- **框架**: Kratos + Gin
- **OLAP**: ClickHouse
- **OLTP**: PostgreSQL
- **依赖注入**: Wire

## 🚀 快速开始

### 本地开发

```bash
# 安装依赖
go mod download

# 生成 Wire 代码
make wire

# 构建
make build

# 运行
make run
```

### 配置环境变量

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=voicehelper

export CLICKHOUSE_ADDR=localhost:9000
export CLICKHOUSE_DB=voicehelper
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=

export PORT=8080
```

## 📡 API 端点

### 1. 使用统计

```bash
GET /api/v1/stats/usage?tenant_id=xxx&period=day&start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
```

**响应示例**:

```json
{
  "tenant_id": "tenant_123",
  "total_conversations": 1000,
  "total_messages": 5000,
  "total_tokens": 100000,
  "total_cost": 50.5,
  "active_users": 100,
  "period": "day",
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2025-01-31T23:59:59Z"
}
```

### 2. 模型统计

```bash
GET /api/v1/stats/model?tenant_id=xxx&period=day&start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
```

### 3. 用户行为统计

```bash
GET /api/v1/stats/user/:user_id?tenant_id=xxx&period=day&start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
```

### 4. 实时统计

```bash
GET /api/v1/stats/realtime?tenant_id=xxx
```

**响应示例**:

```json
{
  "tenant_id": "tenant_123",
  "current_qps": 15.5,
  "current_active_users": 50,
  "current_latency": 250.5,
  "timestamp": "2025-10-26T10:30:00Z"
}
```

### 5. 成本分解

```bash
GET /api/v1/stats/cost?tenant_id=xxx&period=day&start=2025-01-01T00:00:00Z&end=2025-01-31T23:59:59Z
```

**响应示例**:

```json
{
  "tenant_id": "tenant_123",
  "model_cost": 40.0,
  "embedding_cost": 8.0,
  "rerank_cost": 2.5,
  "total_cost": 50.5,
  "period": "day",
  "start_time": "2025-01-01T00:00:00Z",
  "end_time": "2025-01-31T23:59:59Z"
}
```

### 6. 创建报表

```bash
POST /api/v1/reports
```

**请求示例**:

```json
{
  "tenant_id": "tenant_123",
  "type": "usage",
  "name": "January Usage Report",
  "created_by": "user_456"
}
```

**响应示例**:

```json
{
  "id": "report_20250126103000",
  "tenant_id": "tenant_123",
  "type": "usage",
  "name": "January Usage Report",
  "status": "pending",
  "created_by": "user_456",
  "created_at": "2025-01-26T10:30:00Z"
}
```

### 7. 获取报表

```bash
GET /api/v1/reports/:id
```

### 8. 列出报表

```bash
GET /api/v1/reports?tenant_id=xxx&limit=20&offset=0
```

### 9. 删除报表

```bash
DELETE /api/v1/reports/:id
```

## 配置说明

| 配置项            | 说明              | 默认值         |
| ----------------- | ----------------- | -------------- |
| `DB_HOST`         | PostgreSQL 主机   | localhost      |
| `DB_PORT`         | PostgreSQL 端口   | 5432           |
| `CLICKHOUSE_ADDR` | ClickHouse 地址   | localhost:9000 |
| `CLICKHOUSE_DB`   | ClickHouse 数据库 | voicehelper    |
| `PORT`            | 服务端口          | 8080           |

## 架构设计

### DDD 分层架构

```
┌─────────────────────────────────────┐
│          HTTP Server (Gin)          │
├─────────────────────────────────────┤
│       Service Layer (实现接口)      │
├─────────────────────────────────────┤
│     Biz Layer (业务逻辑用例)        │
├─────────────────────────────────────┤
│    Domain Layer (领域模型+接口)     │
├─────────────────────────────────────┤
│    Data Layer (仓储实现)            │
│  ┌──────────────┬─────────────────┐ │
│  │  PostgreSQL  │   ClickHouse    │ │
│  │  (Reports)   │   (Metrics)     │ │
│  └──────────────┴─────────────────┘ │
└─────────────────────────────────────┘
```

### 数据流

```
HTTP Request
    |
    v
Service Layer
    |
    v
Biz Layer (Usecase)
    |
    v
Domain Repository Interface
    |
    v
Data Layer Implementation
    |
    ├─> PostgreSQL (报表元数据)
    └─> ClickHouse (指标数据)
```

## 监控指标

- `analytics_query_duration_seconds`: 查询延迟
- `analytics_report_generation_duration_seconds`: 报表生成延迟
- `analytics_active_queries`: 活跃查询数
- `clickhouse_connection_pool_size`: ClickHouse 连接池大小

## 开发指南

### 添加新的统计类型

1. 在 `internal/domain/metric.go` 定义新的统计结构
2. 在 `MetricRepository` 接口添加查询方法
3. 在 `internal/data/metric_repo.go` 实现查询逻辑
4. 在 `MetricUsecase` 添加业务逻辑
5. 在 HTTP Server 添加 API 端点

### 添加新的报表类型

1. 在 `internal/domain/report.go` 添加报表类型常量
2. 在 `ReportUsecase.generateReportAsync` 添加生成逻辑
3. 实现对应的生成方法

## 📚 相关文档

- [ClickHouse](https://clickhouse.com/docs)
- [Kratos](https://go-kratos.dev/)
- [Wire](https://github.com/google/wire)

## 📝 License

MIT License
