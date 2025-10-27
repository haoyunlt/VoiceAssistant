# Conversation Service

对话管理服务 - 提供对话和消息管理功能。

## 🎯 核心功能

- **对话管理**: 创建、获取、更新、归档、删除对话
- **消息管理**: 发送消息、获取消息、列出消息历史
- **上下文管理**: 自动管理对话上下文、Token 限制
- **多模态支持**: 文本、语音、视频对话
- **权限控制**: 用户级别权限检查
- **多租户支持**: 租户级别数据隔离

## 📋 技术栈

- **框架**: Kratos + Gin
- **数据库**: PostgreSQL
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
export DB_NAME=voiceassistant
export PORT=8080
```

## 📡 API 端点

### 1. 创建对话

```bash
POST /api/v1/conversations
```

**请求示例**:

```json
{
  "tenant_id": "tenant_123",
  "user_id": "user_456",
  "title": "产品咨询",
  "mode": "text"
}
```

**响应示例**:

```json
{
  "id": "conv_20250126103000",
  "tenant_id": "tenant_123",
  "user_id": "user_456",
  "title": "产品咨询",
  "mode": "text",
  "status": "active",
  "context": {
    "max_messages": 100,
    "current_messages": 0,
    "token_limit": 4000,
    "current_tokens": 0
  },
  "created_at": "2025-01-26T10:30:00Z",
  "updated_at": "2025-01-26T10:30:00Z",
  "last_active_at": "2025-01-26T10:30:00Z"
}
```

### 2. 获取对话

```bash
GET /api/v1/conversations/:id?user_id=xxx
```

### 3. 更新对话标题

```bash
PUT /api/v1/conversations/:id
```

**请求示例**:

```json
{
  "user_id": "user_456",
  "title": "新标题"
}
```

### 4. 归档对话

```bash
POST /api/v1/conversations/:id/archive?user_id=xxx
```

### 5. 删除对话

```bash
DELETE /api/v1/conversations/:id?user_id=xxx
```

### 6. 列出对话

```bash
GET /api/v1/conversations?tenant_id=xxx&user_id=xxx&limit=20&offset=0
```

**响应示例**:

```json
{
  "conversations": [
    {
      "id": "conv_20250126103000",
      "title": "产品咨询",
      "mode": "text",
      "status": "active",
      "last_active_at": "2025-01-26T10:30:00Z"
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

### 7. 发送消息

```bash
POST /api/v1/conversations/:id/messages
```

**请求示例**:

```json
{
  "user_id": "user_456",
  "role": "user",
  "content": "你好，我想咨询一下产品价格"
}
```

**响应示例**:

```json
{
  "id": "msg_20250126103005",
  "conversation_id": "conv_20250126103000",
  "tenant_id": "tenant_123",
  "user_id": "user_456",
  "role": "user",
  "content": "你好，我想咨询一下产品价格",
  "content_type": "text",
  "tokens": 15,
  "created_at": "2025-01-26T10:30:05Z"
}
```

### 8. 列出消息

```bash
GET /api/v1/conversations/:id/messages?user_id=xxx&limit=50&offset=0
```

### 9. 获取最近消息

```bash
GET /api/v1/conversations/:id/messages/recent?user_id=xxx&limit=10
```

### 10. 获取单条消息

```bash
GET /api/v1/messages/:id?user_id=xxx
```

## 配置说明

| 配置项        | 说明            | 默认值      |
| ------------- | --------------- | ----------- |
| `DB_HOST`     | PostgreSQL 主机 | localhost   |
| `DB_PORT`     | PostgreSQL 端口 | 5432        |
| `DB_USER`     | 数据库用户      | postgres    |
| `DB_PASSWORD` | 数据库密码      | postgres    |
| `DB_NAME`     | 数据库名        | voiceassistant |
| `PORT`        | 服务端口        | 8080        |

## 架构设计

### DDD 分层架构

```
┌─────────────────────────────────────┐
│          HTTP Server (Gin)          │
├─────────────────────────────────────┤
│       Service Layer (实现接口)      │
├─────────────────────────────────────┤
│     Biz Layer (业务逻辑用例)        │
│  ┌────────────────┬───────────────┐ │
│  │ ConversationUc │  MessageUc    │ │
│  └────────────────┴───────────────┘ │
├─────────────────────────────────────┤
│    Domain Layer (领域模型+接口)     │
│  ┌────────────────┬───────────────┐ │
│  │  Conversation  │    Message    │ │
│  └────────────────┴───────────────┘ │
├─────────────────────────────────────┤
│    Data Layer (仓储实现)            │
│         ┌──────────────┐            │
│         │  PostgreSQL  │            │
│         └──────────────┘            │
└─────────────────────────────────────┘
```

### 数据模型

**对话 (Conversation)**:

- 对话模式: text, voice, video
- 对话状态: active, paused, archived, deleted
- 上下文管理: 消息数限制、Token 限制

**消息 (Message)**:

- 消息角色: user, assistant, system, tool
- 内容类型: text, audio, image, video

## 监控指标

- `conversation_create_duration_seconds`: 创建对话延迟
- `message_send_duration_seconds`: 发送消息延迟
- `conversation_active_count`: 活跃对话数
- `message_total_count`: 总消息数

## 开发指南

### 添加新的对话模式

1. 在 `domain/conversation.go` 添加新的 `ConversationMode`
2. 更新业务逻辑验证
3. 更新 API 文档

### 添加新的消息类型

1. 在 `domain/message.go` 添加新的 `ContentType`
2. 实现对应的处理逻辑
3. 更新 API 文档

## 📚 相关文档

- [Kratos](https://go-kratos.dev/)
- [Gin Web Framework](https://gin-gonic.com/)
- [Wire](https://github.com/google/wire)
- [GORM](https://gorm.io/)

## 📝 License

MIT License
