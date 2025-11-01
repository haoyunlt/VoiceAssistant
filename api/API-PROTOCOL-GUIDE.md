# VoiceHelper API 协议说明

> **更新日期**: 2025-11-01
> **版本**: v1.0

---

## 📋 概述

VoiceHelper 系统使用 **混合协议架构**：
- **Go 后端服务**: gRPC（服务间通信）
- **Python 算法服务**: HTTP/JSON (REST + FastAPI)
- **前端 API**: REST API (通过 Gateway)

## 🏗️ 协议架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端/客户端                             │
│                     (REST API / WebSocket)                    │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                              │
│                  (Kong / Istio / APISIX)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓ gRPC
┌─────────────────────────────────────────────────────────────┐
│                    Go 后端服务层                               │
│    identity, conversation, ai-orchestrator, model-router     │
│                      (gRPC Protocol)                          │
└─────────────────────────────────────────────────────────────┘
                              ↓ HTTP/JSON
┌─────────────────────────────────────────────────────────────┐
│                  Python 算法服务层                             │
│  agent-engine, retrieval-service, model-adapter, ...         │
│                (FastAPI HTTP/JSON Protocol)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔌 协议详解

### 1. Go 后端服务 (gRPC)

#### 服务列表

| 服务 | 端口 | Proto 文件 | 说明 |
|------|------|-----------|------|
| identity-service | 50051 | `api/proto/identity/v1/identity.proto` | 认证授权 |
| conversation-service | 50052 | `api/proto/conversation/v1/conversation.proto` | 对话管理 |
| ai-orchestrator | 50054 | `api/proto/ai-orchestrator/v1/orchestrator.proto` | AI 编排 |
| model-router | 50055 | `api/proto/model-router/v1/model_router.proto` | 模型路由 |
| analytics-service | 50056 | `api/proto/analytics/v1/analytics.proto` | 分析统计 |
| notification-service | 50057 | `api/proto/notification/v1/notification.proto` | 通知推送 |

#### 特点

- ✅ **类型安全**: Protocol Buffers 强类型
- ✅ **性能优越**: 二进制协议，速度快
- ✅ **流式支持**: 支持双向流
- ✅ **代码生成**: 自动生成客户端和服务端代码

#### Proto 定义与实现

**重要说明**: Proto 文件定义了 gRPC 接口规范，但实际服务间调用可能使用不同协议：

- **Go ↔ Go**: 使用 gRPC (完全遵循 proto 定义)
- **Go ↔ Python**: 使用 HTTP/JSON (proto 仅作为接口文档)

---

### 2. Python 算法服务 (HTTP/JSON)

#### 服务列表

| 服务 | 端口 | API 文档 | 说明 |
|------|------|----------|------|
| agent-engine | 8010 | http://localhost:8010/docs | Agent 执行引擎 |
| retrieval-service | 8012 | http://localhost:8012/docs | 混合检索服务 |
| knowledge-service | 8006 | http://localhost:8006/docs | 知识图谱服务 |
| model-adapter | 8005 | http://localhost:8005/docs | LLM 适配器 |
| voice-engine | 8004 | http://localhost:8004/docs | 语音处理 |
| multimodal-engine | 8008 | http://localhost:8008/docs | 多模态处理 |
| indexing-service | 8011 | http://localhost:8011/docs | 文档索引 |
| vector-store-adapter | 8009 | http://localhost:8009/docs | 向量数据库适配 |

#### 特点

- ✅ **易于调试**: 可读的 JSON 格式
- ✅ **FastAPI**: 自动生成 OpenAPI 文档
- ✅ **WebSocket 支持**: 流式响应
- ✅ **灵活性**: 快速迭代和修改

#### API 规范

所有 Python 服务遵循统一的 API 规范：

```python
# 成功响应
{
    "status": "success",  # 可选
    "data": {...},        # 实际数据
    "metadata": {...}     # 元数据（可选）
}

# 错误响应
{
    "detail": "Error message",
    "status_code": 400
}
```

---

## 🔄 协议转换

### Go 调用 Python 服务

Go 服务通过 **HTTP/JSON** 调用 Python 服务：

```go
// pkg/clients/algo/base_client.go
client := algo.NewBaseClient(algo.BaseClientConfig{
    ServiceName: "agent-engine",
    BaseURL:     "http://agent-engine:8010",
    Timeout:     60 * time.Second,
})

// POST /execute
var result AgentResponse
err := client.Post(ctx, "/execute", requestBody, &result)
```

**转换层**: `pkg/clients/algo/`
- `base_client.go`: HTTP 客户端基类
- `client_manager.go`: 客户端管理器
- 各服务专用客户端: `*_client.go`

### Python 调用 Python 服务

Python 服务间使用统一的服务客户端：

```python
# algo/common/service_client.py
from service_client import get_client

retrieval_client = get_client("retrieval-service", "http://retrieval-service:8012")
result = await retrieval_client.post("/api/v1/retrieval/hybrid", {...})
```

---

## 📚 Proto 文件说明

### Proto 文件的角色

| Proto 文件 | 用途 | 实际协议 |
|-----------|------|----------|
| `identity/*.proto` | 定义 gRPC 接口 | ✅ gRPC (Go ↔ Go) |
| `conversation/*.proto` | 定义 gRPC 接口 | ✅ gRPC (Go ↔ Go) |
| `agent/*.proto` | **接口文档** | ⚠️ HTTP/JSON (Go ↔ Python) |
| `rag/*.proto` | **接口文档** | ⚠️ HTTP/JSON (Go ↔ Python) |
| `retrieval/*.proto` | **接口文档** | ⚠️ HTTP/JSON (Go ↔ Python) |

**重要**: 标记为"接口文档"的 proto 文件**不生成实际的 gRPC 代码**，仅用于：
1. 📖 接口规范说明
2. 📝 类型定义参考
3. 🔄 未来可能的 gRPC 迁移

### 为什么使用 HTTP 而不是 gRPC？

**原因**:
1. **生态成熟**: Python 的 FastAPI 生态更成熟
2. **调试便利**: HTTP/JSON 易于调试和测试
3. **灵活性**: 快速迭代算法服务
4. **性能足够**: 算法计算时间 >> 网络传输时间

**未来计划**:
- 可选的 gRPC 支持（通过 grpc-gateway）
- 保持 HTTP 和 gRPC 双协议支持

---

## 🛠️ 开发指南

### 添加新的 Python 算法服务

1. **创建 FastAPI 应用**

```python
from fastapi import FastAPI

app = FastAPI(
    title="My Service",
    description="Service description",
    version="1.0.0",
)

@app.post("/api/v1/process")
async def process(request: ProcessRequest):
    return {"status": "success", "data": {...}}
```

2. **添加到配置文件**

```yaml
# configs/services.yaml
http_services:
  my-service:
    url: "http://localhost:8020"
    timeout: 30s
    description: "My new service"
```

3. **创建 Go 客户端**

```go
// pkg/clients/algo/my_service_client.go
type MyServiceClient struct {
    *BaseClient
}

func NewMyServiceClient(baseURL string) *MyServiceClient {
    return &MyServiceClient{
        BaseClient: NewBaseClient(BaseClientConfig{
            ServiceName: "my-service",
            BaseURL:     baseURL,
            Timeout:     30 * time.Second,
        }),
    }
}
```

4. **（可选）添加 Proto 定义**

```protobuf
// api/proto/my-service/v1/my_service.proto
syntax = "proto3";

package myservice.v1;

// 注意：这是接口文档，实际使用 HTTP/JSON
service MyService {
  rpc Process(ProcessRequest) returns (ProcessResponse);
}
```

### 添加新的 Go 后端服务

1. **定义 Proto**

```protobuf
// api/proto/my-go-service/v1/service.proto
syntax = "proto3";
package mygoservice.v1;

service MyGoService {
  rpc DoSomething(Request) returns (Response);
}
```

2. **生成代码**

```bash
./scripts/proto-gen.sh
```

3. **实现服务**

```go
type server struct {
    pb.UnimplementedMyGoServiceServer
}

func (s *server) DoSomething(ctx context.Context, req *pb.Request) (*pb.Response, error) {
    return &pb.Response{...}, nil
}
```

---

## 🔐 认证与授权

### Token 传递

所有服务间调用都应传递认证 Token：

```
Authorization: Bearer <jwt-token>
X-Request-ID: <request-id>
X-Tenant-ID: <tenant-id>
```

### 实现

**Go 服务**:
```go
// pkg/middleware/auth.go
func WithAuth(ctx context.Context) context.Context {
    // 从 metadata 中提取 token
    md, _ := metadata.FromIncomingContext(ctx)
    // 验证 token
    // ...
    return ctx
}
```

**Python 服务**:
```python
# algo/common/auth_middleware.py
from fastapi import Header

async def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401)
    # 验证 token
    return decoded_token
```

---

## 📊 性能对比

| 协议 | 延迟 | 吞吐量 | 可读性 | 使用场景 |
|------|------|--------|--------|----------|
| gRPC | 低 (1-2ms) | 高 | 低 | Go ↔ Go 内部通信 |
| HTTP/JSON | 中 (3-5ms) | 中 | 高 | Go ↔ Python, 外部 API |
| HTTP/SSE | 中 | 中 | 高 | 流式响应 |
| WebSocket | 低 | 高 | 中 | 实时双向通信 |

**结论**: 对于算法服务，计算时间 (100ms-5s) 远大于网络传输时间 (3-5ms)，HTTP/JSON 是合适的选择。

---

## 🚀 最佳实践

### 1. 使用统一客户端

**Go**:
```go
// 使用 algo.ClientManager
manager, _ := algo.NewClientManagerFromEnv()
result, err := manager.AgentEngine.Post(ctx, "/execute", req, &resp)
```

**Python**:
```python
# 使用 service_client.BaseServiceClient
from service_client import get_client
client = get_client("retrieval-service", base_url)
result = await client.post("/api/v1/retrieval/hybrid", {...})
```

### 2. 超时控制

设置合理的超时时间：
- **短任务** (检索、查询): 10-30s
- **中等任务** (RAG生成): 30-60s
- **长任务** (Agent执行、索引构建): 60-300s

### 3. 错误处理

所有服务调用应处理：
- ✅ 网络错误 (超时、连接失败)
- ✅ HTTP 错误 (4xx, 5xx)
- ✅ 熔断器打开
- ✅ 序列化/反序列化错误

### 4. 监控和追踪

- ✅ 所有请求添加 trace ID
- ✅ 记录请求耗时
- ✅ 监控熔断器状态
- ✅ 记录失败和重试次数

---

## 📞 联系与支持

- **文档问题**: 提交 Issue 或 PR
- **协议讨论**: Slack #voicehelper-architecture
- **性能优化**: Slack #voicehelper-performance

---

**最后更新**: 2025-11-01
**维护者**: VoiceHelper Architecture Team
