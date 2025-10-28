# Identity Service 部署指南

## 编译状态

✅ 服务已成功编译！二进制文件位置：`bin/identity-service` (43MB)

## 已解决的编译问题

1. **Wire 依赖注入问题**
   - 修复了 OAuth 客户端类型冲突（创建了 WechatClient、GithubClient、GoogleClient 包装类型）
   - 添加了缺失的仓库提供者（AuditLogRepository、OAuthRepository）

2. **Proto 代码生成**
   - 生成了 gRPC 和 protobuf 代码
   - 修复了生成文件的位置（移动到正确的 api/proto 目录）

3. **编译错误修复**
   - 修复了 proto 定义与服务实现不匹配的问题
   - 修复了 ClickHouse API 调用问题（sql.ErrNoRows, Exec 返回值）
   - 修复了语法错误（user_repository.go 中的空格）
   - 更新了 gRPC/HTTP 服务注册函数名称

4. **配置文件更新**
   - 添加了完整的 Auth 配置（JWT、OAuth、密码策略）

## 部署前提条件

### 1. 启动 Docker Daemon

```bash
# macOS
open -a Docker

# 或通过命令行
colima start
```

### 2. 启动依赖服务

使用 docker-compose 启动所需的基础设施：

```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
docker-compose up -d postgres redis vault
```

等待服务就绪：

```bash
docker-compose ps
```

### 3. 运行数据库迁移

```bash
# 确保数据库表结构已创建
docker exec -it identity-postgres psql -U voicehelper -d voicehelper -f /docker-entrypoint-initdb.d/001_init_schema.sql
```

## 本地运行

### 方式1：直接运行二进制

```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
./bin/identity-service -conf ../../configs/app/identity-service.yaml
```

### 方式2：使用 Go run

```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
go run . -conf ../../configs/app/identity-service.yaml
```

### 方式3：使用 Makefile

```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
make run
```

## Docker 部署

### 构建镜像

```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
docker build -t voicehelper/identity-service:latest .
```

### 启动完整服务栈

```bash
docker-compose up -d
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 只查看 identity-service 日志
docker-compose logs -f identity-service
```

### 停止服务

```bash
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

## 健康检查

### gRPC 端口（9000）

```bash
# 使用 grpcurl 测试
grpcurl -plaintext localhost:9000 list

# 或使用 gRPC 健康检查
grpcurl -plaintext localhost:9000 grpc.health.v1.Health/Check
```

### HTTP 端口（8000）

```bash
# 健康检查端点（如果实现）
curl http://localhost:8000/health

# 或简单测试端口是否开放
nc -zv localhost 8000
```

## 配置说明

配置文件：`configs/app/identity-service.yaml`

### 关键配置项

1. **数据库连接**
   ```yaml
   data:
     database:
       driver: postgres
       source: postgres://user:pass@host:5432/db?sslmode=disable
   ```

2. **Redis 配置**
   ```yaml
   data:
     redis:
       addr: localhost:6379
       db: 0
   ```

3. **JWT 密钥**（生产环境必须更改！）
   ```yaml
   auth:
     jwt_secret: "your-super-secret-jwt-key-change-this-in-production"
   ```

4. **OAuth 配置**（需要配置真实的凭据）
   ```yaml
   auth:
     oauth:
       wechat:
         app_id: "your-wechat-app-id"
         app_secret: "your-wechat-app-secret"
       github:
         client_id: "your-github-client-id"
         client_secret: "your-github-client-secret"
   ```

## 常见问题

### 1. 无法连接数据库

**错误**: `connection refused` 或 `timeout`

**解决**:
- 确保 PostgreSQL 服务已启动：`docker ps | grep postgres`
- 检查配置文件中的数据库地址和凭据
- 本地运行时使用 `localhost`，Docker 中使用 `postgres`

### 2. Redis 连接失败

**解决**:
- 确保 Redis 服务已启动：`docker ps | grep redis`
- 检查 Redis 地址配置

### 3. 端口已被占用

**错误**: `bind: address already in use`

**解决**:
```bash
# 查找占用端口的进程
lsof -i :8000
lsof -i :9000

# 杀死进程
kill -9 <PID>
```

### 4. Wire 代码未生成

**解决**:
```bash
cd /Users/lintao/important/ai-customer/VoiceHelper/cmd/identity-service
wire
```

### 5. Proto 代码未生成

**解决**:
```bash
cd /Users/lintao/important/ai-customer/VoiceHelper
bash scripts/proto-gen.sh

# 确保生成的文件在正确位置
ls -la api/proto/identity/v1/*.pb.go
```

## 下一步

1. 启动 Docker daemon
2. 运行 `docker-compose up -d` 启动所有服务
3. 查看日志确认服务正常启动
4. 运行集成测试验证功能
5. 配置真实的 OAuth 凭据（如需使用 OAuth 功能）

## 性能和监控

- **指标暴露**: 服务暴露 Prometheus 指标（如果配置）
- **追踪**: OpenTelemetry 追踪发送到 OTEL collector (端口 4317)
- **日志**: 结构化日志输出到 stdout

## 安全注意事项

⚠️ **生产环境部署前必须修改**:

1. JWT 密钥（使用强随机密钥）
2. 数据库密码
3. OAuth 客户端凭据（配置真实值）
4. Redis 密码（生产环境建议启用）
5. 启用 TLS/SSL
6. 配置防火墙规则
7. 使用环境变量或密钥管理服务存储敏感信息

## 支持

如遇问题，请检查：
1. Docker daemon 是否运行
2. 所有依赖服务是否健康
3. 配置文件是否正确
4. 日志输出中的错误信息
