# Notification Service

通知服务负责处理各种通知渠道（邮件、短信、WebSocket、站内消息等）的统一发送。

## 架构

本服务采用 Kratos 框架 + DDD（领域驱动设计）架构：

```
notification-service/
├── main.go                  # 应用入口
├── config.go                # 配置定义
├── wire.go                  # 依赖注入
├── internal/
│   ├── domain/              # 领域模型层
│   │   ├── notification.go  # 通知领域模型和接口
│   │   └── errors.go        # 领域错误
│   ├── data/                # 数据访问层
│   │   ├── data.go          # Data 容器
│   │   ├── db.go            # 数据库连接
│   │   ├── notification_repo.go  # 通知仓储实现
│   │   └── template_repo.go     # 模板仓储实现
│   ├── biz/                 # 业务逻辑层
│   │   ├── notification_usecase.go  # 通知用例
│   │   └── template_usecase.go      # 模板用例
│   ├── service/             # 服务层（适配 gRPC/HTTP）
│   │   └── notification_service.go
│   ├── server/              # 服务器层
│   │   ├── http.go          # HTTP 服务器
│   │   └── grpc.go          # gRPC 服务器
│   └── infra/               # 基础设施层
│       └── providers.go     # 邮件、短信、WebSocket 提供者
└── configs/
    └── notification-service.yaml  # 配置文件
```

## 功能特性

### 已实现

- ✅ 多渠道支持：Email、SMS、WebSocket、InApp
- ✅ 模板管理：支持模板变量渲染
- ✅ 异步发送：后台异步处理通知发送
- ✅ 重试机制：失败自动重试（最多3次）
- ✅ 已读/未读：支持标记已读和未读计数
- ✅ 多租户支持：按 tenantID 隔离
- ✅ 分页查询：支持通知列表分页
- ✅ 健康检查：/health 和 /ready 端点
- ✅ OpenTelemetry 集成：分布式追踪
- ✅ 结构化日志：Kratos 日志框架
- ✅ 依赖注入：Wire DI

### 待实现

- ⏳ 定时发送：支持预约发送时间
- ⏳ 批量发送优化：使用消息队列
- ⏳ Prometheus 指标：发送成功率、延迟等
- ⏳ 真实邮件/短信提供商集成
- ⏳ WebSocket 连接管理
- ⏳ gRPC/HTTP API 完整实现

## 配置

参考 `configs/notification-service.yaml`:

```yaml
server:
  http:
    addr: ":8005"
    timeout: 30
  grpc:
    addr: ":9005"
    timeout: 30

data:
  database:
    driver: postgres
    source: "host=localhost port=5432 user=voicehelper password=voicehelper dbname=notification_service sslmode=disable"
  redis:
    addr: "localhost:6379"
    password: ""
    db: 0

notification:
  max_retries: 3
  retry_interval: 2
  email_from: "noreply@voiceassistant.com"
  sms_provider: "mock"
```

## 运行

### 本地开发

1. 安装依赖：
```bash
go mod download
```

2. 启动 PostgreSQL：
```bash
docker run -d \
  --name notification-postgres \
  -e POSTGRES_USER=voicehelper \
  -e POSTGRES_PASSWORD=voicehelper \
  -e POSTGRES_DB=notification_service \
  -p 5432:5432 \
  postgres:14
```

3. 生成 wire 代码：
```bash
cd cmd/notification-service
wire
```

4. 运行服务：
```bash
go run . -conf ../../configs/notification-service.yaml
```

### 使用 Docker

```bash
docker build -t notification-service .
docker run -p 8005:8005 -p 9005:9005 notification-service
```

## API 示例

### HTTP API

#### 发送通知

```bash
curl -X POST http://localhost:8005/api/v1/notifications \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "tenant-001",
    "user_id": "user-001",
    "recipient": "user@example.com",
    "channel": "email",
    "priority": "high",
    "title": "Welcome",
    "content": "Welcome to VoiceHelper!"
  }'
```

#### 健康检查

```bash
curl http://localhost:8005/health
curl http://localhost:8005/ready
```

## 数据模型

### Notification

```go
type Notification struct {
    ID        string                   // 唯一 ID (UUID)
    TenantID  string                   // 租户 ID
    UserID    string                   // 用户 ID
    Channel   NotificationChannel      // 渠道：email, sms, websocket, inapp
    Priority  NotificationPriority     // 优先级：low, medium, high, critical
    Title     string                   // 标题
    Content   string                   // 内容
    Status    NotificationStatus       // 状态：pending, sending, sent, failed
    Recipient string                   // 收件人（邮箱、手机号等）
    SentAt    *time.Time              // 发送时间
    ReadAt    *time.Time              // 已读时间
    Metadata  MetadataMap             // 元数据 (JSONB)
    ErrorMsg  string                  // 错误消息
    Attempts  int                     // 重试次数
    CreatedAt time.Time               // 创建时间
    UpdatedAt time.Time               // 更新时间
}
```

### Template

```go
type Template struct {
    ID          string       // 唯一 ID (UUID)
    TenantID    string       // 租户 ID
    Name        string       // 模板名称
    Type        TemplateType // 类型：email, sms, websocket, inapp
    Title       string       // 标题模板
    Content     string       // 内容模板
    Description string       // 描述
    Variables   []string     // 变量列表
    IsActive    bool         // 是否激活
    CreatedAt   time.Time    // 创建时间
    UpdatedAt   time.Time    // 更新时间
}
```

## 代码改进说明

本次重构修复了以下问题：

### 1. 架构统一
- ❌ 旧：main.go 使用 Gin 框架，internal/ 使用 Kratos 框架，两套实现并存
- ✅ 新：统一使用 Kratos 框架 + DDD 分层架构

### 2. 类型安全
- ❌ 旧：`req["type"].(string)` 不安全的类型断言
- ✅ 新：强类型结构体 + 验证

### 3. 函数实现
- ❌ 旧：`replaceAll()` 函数为空实现
- ✅ 新：使用 `strings.ReplaceAll()` 正确实现

### 4. Context 管理
- ❌ 旧：goroutine 中使用 `context.Background()`
- ✅ 新：创建带值的 context，便于追踪

### 5. 接口一致性
- ❌ 旧：Repository 接口缺少 `context.Context` 参数
- ✅ 新：所有接口方法都接受 context

### 6. 依赖注入
- ❌ 旧：wire.go 引用未定义的 `newApp` 函数
- ✅ 新：完整的 Provider 定义和配置提取函数

### 7. 错误处理
- ❌ 旧：缺少日志和错误处理
- ✅ 新：结构化日志 + 错误包装

### 8. 可观测性
- ❌ 旧：缺少 tracing 和 metrics
- ✅ 新：OpenTelemetry 集成 + 日志记录

## 监控与告警

### Metrics (待实现)

- `notification_send_total`: 发送总数
- `notification_send_success`: 成功数
- `notification_send_failed`: 失败数
- `notification_send_duration`: 发送延迟
- `notification_retry_total`: 重试次数

### Traces

OpenTelemetry 自动追踪所有 HTTP/gRPC 请求。

## 安全考虑

1. **PII 保护**：敏感信息（邮箱、手机号）加密存储
2. **权限控制**：用户只能访问自己的通知
3. **限流**：防止恶意大量发送
4. **审计日志**：记录所有通知发送操作

## 贡献

请遵循项目的 `.cursorrules` 规范：

- 最小化文档，优先代码和注释
- 使用 PR 模板进行变更说明
- 通过 CI 门禁（lint、test、build）

## License

MIT
