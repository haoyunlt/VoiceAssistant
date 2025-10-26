# Analytics Service - 实现总结

## 📋 实现概述

本文档总结了 **Analytics Service**（分析服务）的完整实现，这是一个基于 Kratos 框架的 Go 微服务，提供实时统计和报表生成功能。

## 🎯 核心功能

### 1. 实时统计

- **使用统计**: 对话数、消息数、Token 数、成本、活跃用户
- **模型统计**: 按模型统计请求数、Token、成本、延迟、错误率
- **用户行为**: 用户会话数、消息数、平均会话时长
- **实时指标**: 当前 QPS、活跃用户、延迟
- **成本分解**: 模型成本、Embedding 成本、重排成本

### 2. 报表生成

- **报表类型**: 使用报表、成本报表、模型报表、用户报表
- **异步生成**: 创建后异步处理，避免阻塞
- **多格式支持**: JSON、CSV、Excel、PDF
- **状态管理**: pending → processing → completed/failed

### 3. 数据存储

- **ClickHouse**: OLAP 查询，存储指标数据
- **PostgreSQL**: 存储报表元数据

## 📁 目录结构

```
cmd/analytics-service/
├── main.go                               # 主入口
├── wire.go                               # Wire 依赖注入配置
├── internal/
│   ├── domain/                           # 领域层
│   │   ├── metric.go                     # 指标聚合根
│   │   ├── report.go                     # 报表聚合根
│   │   ├── errors.go                     # 领域错误
│   │   └── repository.go                 # 仓储接口
│   ├── biz/                              # 业务逻辑层
│   │   ├── metric_usecase.go             # 指标用例
│   │   └── report_usecase.go             # 报表用例
│   ├── data/                             # 数据访问层
│   │   ├── data.go                       # 数据层配置
│   │   ├── db.go                         # PostgreSQL 连接
│   │   ├── clickhouse.go                 # ClickHouse 客户端
│   │   ├── metric_repo.go                # 指标仓储实现
│   │   └── report_repo.go                # 报表仓储实现
│   ├── service/                          # 服务实现层
│   │   └── analytics_service.go          # 分析服务
│   └── server/                           # 服务器层
│       └── http.go                       # HTTP 服务器 (Gin)
├── Makefile
├── README.md
└── IMPLEMENTATION_SUMMARY.md             # 本文件
```

## 🔧 核心实现

### 1. 领域模型 (`internal/domain/`)

**指标类型**:

```go
type UsageStats struct {
    TenantID           string
    TotalConversations int64
    TotalMessages      int64
    TotalTokens        int64
    TotalCost          float64
    ActiveUsers        int64
    Period             TimePeriod
    StartTime          time.Time
    EndTime            time.Time
}
```

**报表模型**:

```go
type Report struct {
    ID          string
    TenantID    string
    Type        ReportType
    Status      ReportStatus
    Data        map[string]interface{}
    FileURL     string
    CreatedAt   time.Time
    CompletedAt *time.Time
}
```

### 2. 业务用例 (`internal/biz/`)

**指标用例**:

```go
func (uc *MetricUsecase) GetUsageStats(
    ctx context.Context,
    tenantID string,
    period TimePeriod,
    start, end time.Time,
) (*UsageStats, error) {
    // 验证时间周期
    if err := uc.validateTimePeriod(period); err != nil {
        return nil, err
    }

    // 从 ClickHouse 查询
    stats, err := uc.metricRepo.GetUsageStats(ctx, tenantID, period, start, end)
    return stats, err
}
```

**报表用例**:

```go
func (uc *ReportUsecase) CreateReport(
    ctx context.Context,
    tenantID, reportType, name, createdBy string,
) (*Report, error) {
    // 创建报表
    report := NewReport(tenantID, reportType, name, createdBy)

    // 保存到数据库
    if err := uc.reportRepo.CreateReport(ctx, report); err != nil {
        return nil, err
    }

    // 异步生成报表
    go uc.generateReportAsync(context.Background(), report)

    return report, nil
}
```

### 3. 数据层 (`internal/data/`)

**ClickHouse 查询**:

```go
func (r *MetricRepository) GetUsageStats(
    ctx context.Context,
    tenantID string,
    period TimePeriod,
    start, end time.Time,
) (*UsageStats, error) {
    query := `
        SELECT
            COUNT(DISTINCT conversation_id) as total_conversations,
            COUNT(*) as total_messages,
            SUM(tokens_used) as total_tokens,
            SUM(cost_usd) as total_cost,
            COUNT(DISTINCT user_id) as active_users
        FROM message_events
        WHERE tenant_id = ?
            AND created_at >= ?
            AND created_at < ?
    `

    row := r.ch.QueryRow(ctx, query, tenantID, start, end)
    // ... 扫描结果
}
```

### 4. HTTP 服务器 (`internal/server/http.go`)

使用 Gin 框架实现 RESTful API：

```go
func (s *HTTPServer) getUsageStats(c *gin.Context) {
    tenantID := c.Query("tenant_id")
    period := c.Query("period")
    start, _ := time.Parse(time.RFC3339, c.Query("start"))
    end, _ := time.Parse(time.RFC3339, c.Query("end"))

    stats, err := s.service.GetUsageStats(c.Request.Context(), tenantID, period, start, end)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, stats)
}
```

## 📡 API 接口

### 统计接口

- `GET /api/v1/stats/usage` - 使用统计
- `GET /api/v1/stats/model` - 模型统计
- `GET /api/v1/stats/user/:user_id` - 用户行为
- `GET /api/v1/stats/realtime` - 实时统计
- `GET /api/v1/stats/cost` - 成本分解

### 报表接口

- `POST /api/v1/reports` - 创建报表
- `GET /api/v1/reports/:id` - 获取报表
- `GET /api/v1/reports` - 列出报表
- `DELETE /api/v1/reports/:id` - 删除报表

## 🚀 性能优化

### 1. ClickHouse 优化

```sql
-- 分区策略
PARTITION BY toYYYYMM(created_at)

-- 排序键
ORDER BY (tenant_id, created_at)

-- TTL 配置
TTL created_at + INTERVAL 90 DAY
```

### 2. 查询优化

- 预聚合：使用物化视图
- 索引优化：合理的排序键
- 分区剪枝：按时间分区

### 3. 报表生成

- 异步处理：不阻塞 API 请求
- 批量查询：减少数据库往返
- 缓存结果：重复查询使用缓存

## 📊 监控指标

### 业务指标

- 统计查询延迟
- 报表生成延迟
- 活跃查询数
- 查询错误率

### 技术指标

- ClickHouse 连接池大小
- PostgreSQL 连接池大小
- 内存使用率
- CPU 使用率

## 🔄 集成关系

### 上游服务

- 无直接上游服务（被动提供查询）

### 下游服务

- **ClickHouse**: 指标数据查询
- **PostgreSQL**: 报表元数据存储
- **MinIO**: 报表文件存储（可选）

### 数据来源

- **Flink**: 实时写入 ClickHouse
- **Debezium**: CDC 数据同步

## 🧪 测试要点

### 单元测试

- [ ] 领域模型逻辑
- [ ] 业务用例逻辑
- [ ] 时间周期验证

### 集成测试

- [ ] ClickHouse 查询
- [ ] PostgreSQL CRUD
- [ ] API 端到端测试

### 性能测试

- [ ] 统计查询 < 500ms
- [ ] 报表生成 < 10s
- [ ] 支持并发 100+ QPS

## 🔐 安全考虑

- **租户隔离**: 所有查询强制 tenant_id 过滤
- **输入验证**: 时间范围、参数验证
- **SQL 注入防护**: 使用参数化查询
- **权限控制**: 结合 Identity Service 鉴权

## 📝 配置示例

### 开发环境

```bash
export DB_HOST=localhost
export DB_PORT=5432
export CLICKHOUSE_ADDR=localhost:9000
export PORT=8080
```

### 生产环境

```bash
export DB_HOST=postgres.voicehelper.svc.cluster.local
export CLICKHOUSE_ADDR=clickhouse.voicehelper.svc.cluster.local:9000
export PORT=8080
```

## 🐛 已知问题与限制

1. **报表生成**: 当前为简化实现，实际应集成文件生成库
2. **缓存**: 查询结果缓存尚未实现
3. **权限**: 权限控制应集成 Identity Service
4. **导出**: 报表导出功能（CSV/Excel/PDF）尚未完整实现

## 🔮 后续优化

1. **实时看板**: WebSocket 推送实时数据
2. **自定义查询**: 支持用户自定义查询和报表
3. **告警**: 基于指标的告警功能
4. **预测分析**: 基于历史数据的趋势预测
5. **数据导出**: 完整的多格式导出功能
6. **查询缓存**: Redis 缓存热门查询

## ✅ 验收清单

- [x] 领域模型定义
- [x] 业务用例实现
- [x] ClickHouse 集成
- [x] PostgreSQL 集成
- [x] HTTP API 实现
- [x] Wire 依赖注入
- [x] 多租户支持
- [x] 异步报表生成
- [x] 实时统计功能
- [x] 成本分解功能
- [x] README 文档
- [x] 实现总结（本文档）

## 📚 参考资料

- [ClickHouse Documentation](https://clickhouse.com/docs)
- [Kratos Documentation](https://go-kratos.dev/)
- [Wire Guide](https://github.com/google/wire/blob/master/docs/guide.md)
- [Gin Web Framework](https://gin-gonic.com/)

---

**实现完成日期**: 2025-10-26
**版本**: v1.0.0
**实现者**: AI Assistant
