# VoiceHelper AI API 文档总览

## 简介

VoiceHelper AI 提供 RESTful API 和 gRPC API，支持完整的智能客服功能。

## API 版本

当前版本: **v2.0.0**

## 基础 URL

- 开发环境: `http://localhost:9080`
- 生产环境: `https://api.voicehelper.ai`

## 认证

所有 API 请求（除登录外）需要在 Header 中携带 JWT Token：

```
Authorization: Bearer <your_access_token>
```

## 服务端点

### Identity Service
- **Base Path**: `/api/v1/identity`
- **用途**: 用户认证与授权

### Conversation Service
- **Base Path**: `/api/v1/conversations`
- **用途**: 对话管理

### Knowledge Service
- **Base Path**: `/api/v1/knowledge`
- **用途**: 知识库管理

### AI Orchestrator
- **Base Path**: `/api/v1/ai`
- **用途**: AI 任务编排

## 快速开始

### 1. 用户登录

```bash
curl -X POST http://localhost:9080/api/v1/identity/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 3600,
  "user": {
    "id": "usr_123",
    "email": "user@example.com",
    "username": "john_doe"
  }
}
```

### 2. 创建对话

```bash
curl -X POST http://localhost:9080/api/v1/conversations \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "usr_123",
    "tenant_id": "tenant_123",
    "mode": "text"
  }'
```

### 3. 发送消息

```bash
curl -X POST http://localhost:9080/api/v1/conversations/conv_123/messages \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "你好，有什么可以帮助我的吗？"
  }'
```

## 完整文档

- [OpenAPI 规范](../openapi.yaml)
- [gRPC Proto 定义](../../api/proto/)
- [Postman Collection](./postman/)

## 错误处理

所有错误响应遵循统一格式：

```json
{
  "code": 400,
  "message": "Bad request",
  "details": {}
}
```

常见错误码：
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error

## 限流

- 默认限流: 100 req/min
- 企业版: 1000 req/min

超出限流会返回 `429 Too Many Requests`。

## 更多资源

- [架构文档](../arch/microservice-architecture-v2.md)
- [SDK 文档](../../shared/sdks/)
- [示例代码](../../examples/)

