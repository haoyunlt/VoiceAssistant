# Identity Service

身份认证服务，提供用户管理、租户管理、JWT 认证、OAuth 登录等功能。

## 功能特性

### 已实现功能

- ✅ 用户注册与登录
- ✅ JWT Token 认证（Access Token + Refresh Token）
- ✅ Token 黑名单机制
- ✅ 密码强度验证
- ✅ 邮箱格式验证
- ✅ 多租户支持
- ✅ 角色权限管理
- ✅ Redis 缓存
- ✅ 审计日志（基础）
- ✅ OAuth 登录（框架）
- ✅ 配置化的 Token 过期时间
- ✅ 可配置的密码策略

### 待实现功能

- ⏳ 完整的 OAuth 集成（Google、GitHub、微信）
- ⏳ 密码重置功能
- ⏳ 邮箱验证
- ⏳ 双因素认证（2FA）
- ⏳ 登录限流
- ⏳ 账户锁定机制

## 架构设计

```
┌─────────────┐
│   Client    │
└─────┬───────┘
      │
      ▼
┌─────────────────────┐
│  HTTP/gRPC Server   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Service Layer      │
│  (IdentityService)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────┐
│  Business Logic Layer       │
│  - AuthUsecase             │
│  - UserUsecase             │
│  - TenantUsecase           │
│  - OAuthUsecase            │
└─────────┬───────────────────┘
          │
          ▼
┌──────────────────────────────┐
│  Data Layer                  │
│  - UserRepo                 │
│  - TenantRepo               │
│  - TokenBlacklistService    │
│  - CacheManager             │
└─────────┬────────────────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌────────┐  ┌──────────┐
│ Postgres│  │  Redis   │
└────────┘  └──────────┘
```

## 快速开始

### 前置要求

- Go 1.21+
- PostgreSQL 14+
- Redis 7+
- Wire (依赖注入工具)

### 安装依赖

```bash
# 安装 Wire
go install github.com/google/wire/cmd/wire@latest

# 下载 Go 依赖
cd cmd/identity-service
go mod tidy
```

### 配置

复制示例配置文件并修改：

```bash
cp ../../configs/app/identity-service.yaml.example ../../configs/app/identity-service.yaml
```

编辑配置文件，设置数据库和 Redis 连接：

```yaml
data:
  database:
    driver: postgres
    source: "host=localhost port=5432 user=youruser password=yourpass dbname=yourdb sslmode=disable"
  redis:
    addr: localhost:6379
    password: ""
    db: 0

auth:
  jwt_secret: "your-very-secure-secret-key-change-this"
  access_token_expiry: "1h"
  refresh_token_expiry: "168h"
```

### 运行

```bash
# 生成 Wire 依赖注入代码
cd cmd/identity-service
wire

# 运行服务
go run . -conf ../../configs/app/identity-service.yaml
```

服务将启动在：
- HTTP: `http://localhost:8000`
- gRPC: `localhost:9000`

## API 接口

### HTTP REST API

- `POST /api/v1/identity/login` - 用户登录
- `POST /api/v1/identity/logout` - 用户登出
- `POST /api/v1/identity/refresh-token` - 刷新 Token
- `POST /api/v1/identity/verify-token` - 验证 Token
- `POST /api/v1/identity/users` - 创建用户
- `GET /api/v1/identity/users/:id` - 获取用户信息
- `PUT /api/v1/identity/users/:id` - 更新用户信息
- `DELETE /api/v1/identity/users/:id` - 删除用户
- `POST /api/v1/identity/change-password` - 修改密码

### gRPC API

参考 `api/proto/identity/v1/identity.proto`

## 配置说明

### 服务器配置

```yaml
server:
  http:
    network: tcp
    addr: :8000          # HTTP 监听地址
    timeout: 30s         # 请求超时时间
  grpc:
    network: tcp
    addr: :9000          # gRPC 监听地址
    timeout: 30s
```

### 认证配置

```yaml
auth:
  jwt_secret: "your-secret-key"           # JWT 签名密钥（必须修改）
  access_token_expiry: "1h"               # Access Token 有效期
  refresh_token_expiry: "168h"            # Refresh Token 有效期（7天）

  password_policy:
    min_length: 8                         # 密码最小长度
    require_upper: true                   # 要求大写字母
    require_lower: true                   # 要求小写字母
    require_digit: true                   # 要求数字
    require_special: false                # 要求特殊字符
```

### 数据库配置

```yaml
data:
  database:
    driver: postgres
    source: "host=localhost port=5432 user=postgres password=password dbname=voiceassistant sslmode=disable"

  redis:
    addr: localhost:6379
    password: ""
    db: 0
    pool_size: 10
    min_idle_conns: 5
    read_timeout: 3s
    write_timeout: 3s
```

## 开发指南

### 项目结构

```
cmd/identity-service/
├── main.go                    # 入口文件
├── config.go                  # 配置定义
├── wire.go                    # Wire 依赖注入
├── internal/
│   ├── biz/                   # 业务逻辑层
│   │   ├── auth_usecase.go   # 认证用例
│   │   ├── user_usecase.go   # 用户用例
│   │   └── tenant_usecase.go # 租户用例
│   ├── data/                  # 数据访问层
│   │   ├── user_repo.go      # 用户仓储
│   │   ├── tenant_repo.go    # 租户仓储
│   │   ├── cache.go          # 缓存管理
│   │   └── token_blacklist.go# Token 黑名单
│   ├── domain/                # 领域模型
│   │   ├── user.go           # 用户实体
│   │   ├── tenant.go         # 租户实体
│   │   └── password.go       # 密码验证
│   ├── server/                # 服务器层
│   │   ├── http.go           # HTTP 服务器
│   │   └── grpc.go           # gRPC 服务器
│   └── service/               # 服务接口层
│       └── identity_service.go
└── IMPROVEMENTS.md            # 改进说明文档
```

### 添加新功能

1. **定义领域模型**：在 `internal/domain/` 中定义实体和值对象
2. **实现仓储**：在 `internal/data/` 中实现数据访问
3. **编写业务逻辑**：在 `internal/biz/` 中实现用例
4. **暴露服务接口**：在 `internal/service/` 中实现 gRPC/HTTP 接口
5. **更新 Wire 配置**：在 `wire.go` 中注册依赖

### 运行测试

```bash
# 单元测试
go test ./internal/...

# 集成测试
go test -tags=integration ./...

# 测试覆盖率
go test -cover ./...
```

### 代码检查

```bash
# 运行 linter
golangci-lint run

# 格式化代码
go fmt ./...

# 静态分析
go vet ./...
```

## 安全最佳实践

1. **JWT Secret**：生产环境必须使用强随机密钥，至少 32 字符
2. **密码策略**：根据安全要求调整密码策略
3. **Token 过期时间**：根据业务需求平衡安全和用户体验
4. **HTTPS**：生产环境必须使用 HTTPS
5. **限流**：建议在网关层实现限流，防止暴力破解
6. **审计日志**：重要操作必须记录审计日志

## 监控指标

建议监控以下指标：

- **业务指标**
  - 登录成功率
  - 登录失败率
  - Token 验证成功率
  - 用户注册数

- **性能指标**
  - API 响应时间（P50, P95, P99）
  - Token 验证延迟
  - 数据库查询延迟
  - Redis 操作延迟

- **可用性指标**
  - 服务可用性（SLO: 99.9%）
  - 错误率
  - 依赖服务健康状态

## 故障排查

### 常见问题

**问题：服务启动失败**
```
检查：
1. 数据库连接是否正常
2. Redis 连接是否正常
3. 配置文件路径是否正确
4. 端口是否被占用
```

**问题：Token 验证失败**
```
检查：
1. JWT Secret 是否正确
2. Token 是否过期
3. Token 是否在黑名单中
4. 时钟同步是否正常
```

**问题：Redis 连接超时**
```
检查：
1. Redis 服务是否运行
2. 网络连接是否正常
3. Redis 密码是否正确
4. 连接池配置是否合理
```

## 性能优化

### 缓存策略

- 用户信息缓存：TTL 1小时
- 租户信息缓存：TTL 1小时
- 权限缓存：TTL 10分钟

### 数据库优化

- 在 `email` 字段创建唯一索引
- 在 `tenant_id` 字段创建索引
- 使用连接池
- 定期清理软删除数据

### Redis 优化

- 使用 SCAN 而非 KEYS 命令
- 合理设置过期时间
- 监控内存使用
- 使用 Pipeline 批量操作

## 更多文档

- [改进说明](./IMPROVEMENTS.md) - 详细的代码改进说明
- [API 文档](../../api/proto/identity/v1/identity.proto) - gRPC API 定义
- [部署指南](../../docs/runbook/index.md) - 运维手册

## License

Copyright © 2025 VoiceAssistant Team
