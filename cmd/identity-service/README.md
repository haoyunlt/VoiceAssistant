# Identity Service

用户认证与授权服务，基于 Kratos 框架实现。

## 功能特性

- ✅ 用户注册与登录
- ✅ JWT Token 认证
- ✅ 密码加密（bcrypt）
- ✅ 角色管理（RBAC）
- ✅ 租户管理
- ✅ 用户配额控制
- ✅ Token 刷新机制
- ✅ 用户状态管理

## 项目结构

```
identity-service/
├── main.go                    # 应用入口
├── wire.go                    # Wire 依赖注入配置
├── internal/
│   ├── domain/               # 领域模型
│   │   ├── user.go          # 用户聚合根
│   │   ├── tenant.go        # 租户聚合根
│   │   └── repository.go    # 仓储接口
│   ├── biz/                 # 业务逻辑层
│   │   ├── user_usecase.go  # 用户用例
│   │   ├── auth_usecase.go  # 认证用例
│   │   └── tenant_usecase.go# 租户用例
│   ├── data/                # 数据访问层
│   │   ├── data.go          # 数据层初始化
│   │   ├── db.go            # 数据库连接
│   │   ├── user_repo.go     # 用户仓储实现
│   │   └── tenant_repo.go   # 租户仓储实现
│   ├── service/             # 服务层（gRPC 实现）
│   │   └── identity_service.go
│   └── server/              # 服务器配置
│       ├── grpc.go          # gRPC 服务器
│       └── http.go          # HTTP 服务器
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd cmd/identity-service
go mod tidy
```

### 2. 生成 Wire 代码

```bash
go install github.com/google/wire/cmd/wire@latest
wire
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等
```

### 4. 启动服务

```bash
go run .
```

## API 接口

### gRPC 接口

- `CreateUser` - 创建用户
- `GetUser` - 获取用户信息
- `UpdateUser` - 更新用户信息
- `DeleteUser` - 删除用户
- `Login` - 用户登录

### HTTP 接口（通过 gRPC-Gateway）

- `POST /api/v1/identity/users` - 创建用户
- `GET /api/v1/identity/users/{id}` - 获取用户
- `PUT /api/v1/identity/users/{id}` - 更新用户
- `DELETE /api/v1/identity/users/{id}` - 删除用户
- `POST /api/v1/identity/login` - 登录

## 配置说明

配置文件位于 `../../configs/app/identity-service.yaml`

```yaml
server:
  http:
    addr: 0.0.0.0:8000 # HTTP 服务地址
    timeout: 10s
  grpc:
    addr: 0.0.0.0:9000 # gRPC 服务地址
    timeout: 10s

data:
  database:
    driver: postgres
    source: postgres://user:pass@localhost:5432/dbname
  redis:
    addr: localhost:6379
    read_timeout: 3s
    write_timeout: 3s

jwt_secret: 'your-jwt-secret' # JWT 密钥（生产环境务必修改）
```

## 测试

### 单元测试

```bash
go test ./internal/...
```

### 集成测试

```bash
go test -tags=integration ./...
```

## 开发指南

### 添加新的用例

1. 在 `internal/biz/` 中创建新的 usecase 文件
2. 实现业务逻辑
3. 在 `internal/service/` 中添加 gRPC 方法
4. 更新 `wire.go` 添加依赖注入

### 数据库迁移

使用项目根目录的数据库迁移脚本：

```bash
cd ../..
make migrate-up
```

## 依赖项

- Kratos v2.7+ - 微服务框架
- GORM - ORM
- Wire - 依赖注入
- golang-jwt/jwt - JWT 认证
- bcrypt - 密码加密

## 环境要求

- Go 1.21+
- PostgreSQL 15+
- Redis 7+

## 监控指标

服务暴露以下 Prometheus 指标：

- `http_requests_total` - HTTP 请求总数
- `http_request_duration_seconds` - HTTP 请求延迟
- `grpc_server_handled_total` - gRPC 请求总数
- `grpc_server_handling_seconds` - gRPC 请求延迟

访问 `http://localhost:8000/metrics` 查看指标。

## 故障排查

### 数据库连接失败

检查数据库配置和网络连接：

```bash
psql -h localhost -U voiceassistant -d voiceassistant
```

### JWT Token 无效

确保 `jwt_secret` 配置正确，且 Token 未过期。

### Wire 生成失败

删除旧的生成文件并重新生成：

```bash
rm wire_gen.go
wire
```

## 更多信息

- [Kratos 文档](https://go-kratos.dev/)
- [Wire 文档](https://github.com/google/wire)
- [API 文档](../../docs/api/API_OVERVIEW.md)
