# VoiceHelper API 定义

本目录包含 VoiceHelper 项目的 API 定义和规范。

## 📁 目录结构

```
api/
├── proto/              # gRPC Protocol Buffers 定义
│   ├── identity/       # 认证授权服务
│   ├── conversation/   # 对话服务
│   ├── knowledge/      # 知识服务
│   ├── model-router/   # 模型路由服务
│   ├── ai-orchestrator/# AI 编排服务
│   └── events/         # 事件定义
└── openapi.yaml        # REST API 规范
```

## ⚠️ 重要说明：协议使用

**VoiceHelper 使用混合协议架构**：

- **Go 后端服务间**: gRPC（遵循 proto 定义）
- **Go 调用 Python 算法服务**: HTTP/JSON（proto 文件仅作为接口文档）
- **Python 算法服务间**: HTTP/JSON (FastAPI)

详细说明请参阅：[API 协议指南](./API-PROTOCOL-GUIDE.md)

---

## 🔌 gRPC API

### Protocol Buffers

**Go 后端服务**使用 Protocol Buffers 3 定义 gRPC 接口。

**Python 算法服务**的 proto 文件仅作为**接口文档**，实际使用 HTTP/JSON 协议。

#### 代码生成

```bash
# 生成所有 proto 代码
./scripts/proto-gen.sh

# 生成特定服务
protoc --go_out=. --go-grpc_out=. proto/identity/*.proto
```

#### 服务定义

##### Identity Service

```protobuf
service IdentityService {
  rpc Register(RegisterRequest) returns (RegisterResponse);
  rpc Login(LoginRequest) returns (LoginResponse);
  rpc Verify(VerifyRequest) returns (VerifyResponse);
  rpc GetUser(GetUserRequest) returns (User);
}
```

##### Conversation Service

```protobuf
service ConversationService {
  rpc CreateConversation(CreateConversationRequest) returns (Conversation);
  rpc GetConversation(GetConversationRequest) returns (Conversation);
  rpc ListMessages(ListMessagesRequest) returns (ListMessagesResponse);
  rpc SendMessage(SendMessageRequest) returns (Message);
  rpc StreamChat(stream ChatRequest) returns (stream ChatResponse);
}
```

##### Knowledge Service

```protobuf
service KnowledgeService {
  rpc CreateKnowledgeBase(CreateKBRequest) returns (KnowledgeBase);
  rpc UploadDocument(stream UploadRequest) returns (UploadResponse);
  rpc Search(SearchRequest) returns (SearchResponse);
  rpc DeleteDocument(DeleteDocumentRequest) returns (DeleteResponse);
}
```

##### Model Router

```protobuf
service ModelRouter {
  rpc Route(RouteRequest) returns (RouteResponse);
  rpc Chat(ChatRequest) returns (ChatResponse);
  rpc StreamChat(ChatRequest) returns (stream ChatResponse);
  rpc GetModels(GetModelsRequest) returns (GetModelsResponse);
}
```

### 使用示例

#### Go 客户端

```go
import (
    pb "github.com/voiceassistant/api/proto/identity"
    "google.golang.org/grpc"
)

conn, err := grpc.Dial("identity-service:9000", grpc.WithInsecure())
if err != nil {
    log.Fatal(err)
}
defer conn.Close()

client := pb.NewIdentityServiceClient(conn)
resp, err := client.Login(ctx, &pb.LoginRequest{
    Username: "user@example.com",
    Password: "password",
})
```

#### Python 客户端

```python
import grpc
from proto.identity import identity_pb2, identity_pb2_grpc

channel = grpc.insecure_channel('identity-service:9000')
stub = identity_pb2_grpc.IdentityServiceStub(channel)

response = stub.Login(identity_pb2.LoginRequest(
    username='user@example.com',
    password='password'
))
```

## 🌐 REST API

### OpenAPI 规范

REST API 使用 OpenAPI 3.0 规范定义在 `openapi.yaml`。

#### 主要端点

##### 认证

- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/refresh` - 刷新令牌
- `POST /api/v1/auth/logout` - 用户登出

##### 对话

- `GET /api/v1/conversations` - 获取对话列表
- `POST /api/v1/conversations` - 创建对话
- `GET /api/v1/conversations/{id}` - 获取对话详情
- `DELETE /api/v1/conversations/{id}` - 删除对话
- `POST /api/v1/conversations/{id}/messages` - 发送消息
- `GET /api/v1/conversations/{id}/messages` - 获取消息列表

##### 知识库

- `GET /api/v1/knowledge/bases` - 获取知识库列表
- `POST /api/v1/knowledge/bases` - 创建知识库
- `POST /api/v1/knowledge/bases/{id}/documents` - 上传文档
- `GET /api/v1/knowledge/bases/{id}/documents` - 获取文档列表
- `POST /api/v1/knowledge/search` - 知识搜索

##### AI 服务

- `POST /api/v1/ai/chat` - AI 对话
- `POST /api/v1/ai/chat/stream` - 流式 AI 对话
- `POST /api/v1/ai/complete` - 文本补全

##### 语音

- `WS /ws/voice` - WebSocket 语音流
- `POST /api/v1/voice/asr` - 语音识别
- `POST /api/v1/voice/tts` - 文本转语音

#### 使用示例

##### cURL

```bash
# 用户登录
curl -X POST http://api.voiceassistant.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password"
  }'

# 发送消息（需要认证）
curl -X POST http://api.voiceassistant.com/api/v1/conversations/123/messages \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "你好，请帮我查询订单状态"
  }'
```

##### JavaScript

```javascript
// 使用 Fetch API
const response = await fetch('http://api.voiceassistant.com/api/v1/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    username: 'user@example.com',
    password: 'password',
  }),
});

const data = await response.json();
const token = data.token;

// 流式对话
const eventSource = new EventSource(
  `http://api.voiceassistant.com/api/v1/ai/chat/stream?token=${token}`
);

eventSource.onmessage = (event) => {
  console.log('Response:', event.data);
};
```

##### Python

```python
import requests

# 登录
response = requests.post(
    'http://api.voiceassistant.com/api/v1/auth/login',
    json={
        'username': 'user@example.com',
        'password': 'password'
    }
)
token = response.json()['token']

# 发送消息
response = requests.post(
    'http://api.voiceassistant.com/api/v1/conversations/123/messages',
    headers={'Authorization': f'Bearer {token}'},
    json={'content': '你好，请帮我查询订单状态'}
)
```

## 🔐 认证

所有 API 端点（除了公开端点）都需要认证。

### JWT 认证

1. 通过 `/api/v1/auth/login` 获取 JWT token
2. 在后续请求中添加 `Authorization: Bearer <token>` header

### Token 刷新

Token 有效期为 24 小时，可通过 `/api/v1/auth/refresh` 刷新。

## 📊 响应格式

### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    // 响应数据
  }
}
```

### 错误响应

```json
{
  "code": 400,
  "message": "Invalid request",
  "error": "username is required"
}
```

### 错误码

| 错误码 | 说明           |
| ------ | -------------- |
| 200    | 成功           |
| 400    | 请求参数错误   |
| 401    | 未认证         |
| 403    | 无权限         |
| 404    | 资源不存在     |
| 429    | 请求过于频繁   |
| 500    | 服务器内部错误 |
| 503    | 服务不可用     |

## 📝 API 版本

当前 API 版本：`v1`

版本策略：

- Major 版本：不兼容的 API 更改
- Minor 版本：向后兼容的功能添加
- Patch 版本：向后兼容的错误修复

## 🧪 测试

### Postman Collection

导入 `postman/VoiceHelper.postman_collection.json` 到 Postman。

### API 测试脚本

```bash
./scripts/test-services.sh
```

## 📖 文档

- **OpenAPI Docs**: http://api.voiceassistant.com/docs
- **Swagger UI**: http://api.voiceassistant.com/swagger
- **Redoc**: http://api.voiceassistant.com/redoc

## 🔗 相关链接

- [gRPC 官方文档](https://grpc.io/docs/)
- [Protocol Buffers](https://developers.google.com/protocol-buffers)
- [OpenAPI 规范](https://swagger.io/specification/)

## 🆘 获取帮助

- API 问题：api-support@voiceassistant.com
- Issue：https://github.com/voiceassistant/VoiceHelper/issues
