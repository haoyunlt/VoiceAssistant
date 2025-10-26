# Notification Service

通知服务 - 统一的消息推送、邮件、SMS、Webhook 管理

## 功能特性

### 1. 多渠道支持

- **Email**: SMTP、SendGrid、AWS SES
- **SMS**: Twilio、阿里云、腾讯云
- **Push**: FCM (Firebase Cloud Messaging)、APNs
- **Webhook**: HTTP POST 回调

### 2. 模板管理

- 模板创建与编辑
- 变量替换
- 多语言支持
- 版本控制

### 3. 订阅管理

- 用户订阅偏好
- 事件类型过滤
- 渠道选择
- 频率控制

### 4. 事件驱动

- Kafka 事件消费
- 自动触发通知
- 重试机制
- 失败处理

### 5. 统计与监控

- 发送成功率
- 渠道性能
- 用户参与度
- Prometheus 指标

## API 接口

### POST /api/v1/notifications/send

发送单个通知

**请求**:

```json
{
  "type": "email",
  "recipient": "user@example.com",
  "template_id": "tmpl_123",
  "variables": {
    "user_name": "John Doe",
    "service_name": "VoiceHelper"
  },
  "priority": "normal"
}
```

**响应**:

```json
{
  "notification_id": "notif_123",
  "type": "email",
  "status": "sent",
  "sent_at": "2025-10-26T10:30:00Z"
}
```

### POST /api/v1/notifications/batch

批量发送通知

**请求**:

```json
{
  "notifications": [
    {
      "type": "push",
      "recipient": "device_token_1",
      "title": "New Message",
      "body": "You have a new message"
    },
    ...
  ]
}
```

### POST /api/v1/templates

创建通知模板

**请求**:

```json
{
  "name": "Welcome Email",
  "type": "email",
  "subject": "Welcome to {{service_name}}",
  "body": "Hello {{user_name}}, welcome!",
  "variables": ["service_name", "user_name"]
}
```

### POST /api/v1/subscriptions

创建订阅

**请求**:

```json
{
  "user_id": "user_123",
  "event_types": ["document.uploaded", "document.indexed", "conversation.message"],
  "channels": ["email", "push"],
  "frequency": "realtime"
}
```

## 配置

```yaml
notification:
  channels:
    email:
      provider: smtp
      host: smtp.gmail.com
      port: 587
      username: ${EMAIL_USERNAME}
      password: ${EMAIL_PASSWORD}
      from: noreply@voicehelper.com

    sms:
      provider: twilio
      account_sid: ${TWILIO_ACCOUNT_SID}
      auth_token: ${TWILIO_AUTH_TOKEN}
      from: +1234567890

    push:
      provider: fcm
      api_key: ${FCM_API_KEY}

    webhook:
      timeout: 10s
      retry_times: 3

  kafka:
    brokers:
      - kafka:9092
    topics:
      - conversation.events
      - document.events
      - ai.task.completed
    group_id: notification-consumer

  templates:
    path: /app/templates
    cache_ttl: 1h

  limits:
    max_batch_size: 100
    rate_limit_per_user: 100/hour
```

## 事件订阅

服务自动订阅以下 Kafka 事件：

| 事件                        | 触发通知         |
| --------------------------- | ---------------- |
| `conversation.created`      | 新会话创建通知   |
| `conversation.message.sent` | 新消息通知       |
| `document.uploaded`         | 文档上传成功通知 |
| `document.indexed`          | 文档索引完成通知 |
| `ai.task.completed`         | AI 任务完成通知  |
| `ai.task.failed`            | AI 任务失败告警  |

## 部署

### Docker

```bash
docker build -t notification-service:latest .
docker run -p 9005:9005 notification-service:latest
```

### Kubernetes

```bash
kubectl apply -f deployments/k8s/notification-service.yaml
```

## 监控

Prometheus 指标暴露在 `/metrics`：

- `notification_sent_total` - 总发送数
- `notification_delivered_total` - 总送达数
- `notification_failed_total` - 总失败数
- `notification_send_duration_seconds` - 发送延迟
- `notification_channel_health` - 渠道健康状态

## 开发

### 编译

```bash
go build -o notification-service ./cmd/notification-service
```

### 运行

```bash
./notification-service
```

### 测试

```bash
go test ./...
```
