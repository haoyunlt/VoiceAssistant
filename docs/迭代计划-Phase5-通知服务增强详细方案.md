# Phase 5: 通知服务增强 - 详细实施方案

---

## 📋 基本信息

- **阶段**: Phase 5
- **时间**: Q2 2025, Week 4-6 (3周)
- **目标**: 增强通知分发能力
- **优先级**: 🟢 P2 - 中低优先级
- **前置依赖**: Phase 1 (API Gateway)、Phase 4 (会话管理)
- **负责人**: 后端开发组
- **状态**: 📋 待开始

---

## 🎯 Phase目标

### 主要目标
对齐VoiceHelper的Notification Service能力，实现多渠道通知系统：
1. RabbitMQ消息队列集成
2. WebSocket实时推送
3. 邮件通知（SMTP）
4. 短信通知（可选）
5. 通知模板管理
6. 通知去重机制

### 成功标准
1. ✅ RabbitMQ正常工作，消息可靠传递
2. ✅ WebSocket推送正常，实时性<100ms
3. ✅ 邮件发送成功率>99%
4. ✅ 通知模板系统正常工作
5. ✅ 通知去重有效，避免重复发送
6. ✅ 单元测试覆盖率 > 70%
7. ✅ 集成测试通过率 100%

---

## 📐 架构设计

### 目标架构

```mermaid
flowchart TB
    Services[其他服务]

    subgraph RabbitMQ["RabbitMQ消息队列"]
        Exchange[Exchange<br/>notification-exchange]
        Queue1[Queue<br/>notification-websocket]
        Queue2[Queue<br/>notification-email]
        Queue3[Queue<br/>notification-sms]

        Exchange --> Queue1
        Exchange --> Queue2
        Exchange --> Queue3
    end

    subgraph NotificationService["Notification Service (Port 9004)"]
        Handler[Notification Handler]

        subgraph CoreServices["核心服务"]
            NotifService[Notification Service<br/>通知管理]
            TemplateService[Template Service<br/>模板管理]
            DedupeService[Dedupe Service<br/>去重服务]
        end

        subgraph Workers["消费者Workers"]
            WSWorker[WebSocket Worker]
            EmailWorker[Email Worker]
            SMSWorker[SMS Worker]
        end

        Handler --> NotifService
        NotifService --> TemplateService
        NotifService --> DedupeService

        Queue1 --> WSWorker
        Queue2 --> EmailWorker
        Queue3 --> SMSWorker
    end

    subgraph Channels["通知渠道"]
        WebSocket[WebSocket<br/>实时推送]
        SMTP[SMTP<br/>邮件服务器]
        SMS_API[SMS API<br/>第三方短信]
    end

    subgraph Database["数据存储"]
        Redis[(Redis<br/>去重/缓存)]
        PostgreSQL[(PostgreSQL<br/>通知记录/模板)]
    end

    Services -->|发布消息| Exchange

    WSWorker --> WebSocket
    EmailWorker --> SMTP
    SMSWorker --> SMS_API

    NotifService --> Redis
    NotifService --> PostgreSQL

    style Workers fill:#e1f5ff
    style CoreServices fill:#fff4e1
    style Channels fill:#e1ffe1
```

### 增强的Notification Service结构

```
cmd/notification-service/
├── main.go
├── config/
│   └── config.go
└── internal/
    ├── handler/
    │   └── notification_handler.go    # 新增 ⭐
    ├── service/
    │   ├── notification_service.go    # 新增 ⭐
    │   ├── template_service.go        # 新增 ⭐
    │   └── dedupe_service.go          # 新增 ⭐
    ├── worker/
    │   ├── websocket_worker.go        # 新增 ⭐
    │   ├── email_worker.go            # 新增 ⭐
    │   └── sms_worker.go              # 新增 ⭐
    ├── channel/
    │   ├── websocket_channel.go       # 新增 ⭐
    │   ├── email_channel.go           # 新增 ⭐
    │   └── sms_channel.go             # 新增 ⭐
    ├── repository/
    │   ├── notification_repository.go # 新增 ⭐
    │   └── template_repository.go     # 新增 ⭐
    └── model/
        ├── notification.go            # 新增 ⭐
        └── template.go                # 新增 ⭐
```

---

## 📅 详细任务分解

### Week 1: RabbitMQ集成与基础架构（5天）

#### Task 1.1: RabbitMQ部署 (1天)

**RabbitMQ Deployment**:
```yaml
# deployments/k8s/infrastructure/rabbitmq/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rabbitmq
  namespace: voiceassistant-prod
  labels:
    app: rabbitmq
spec:
  replicas: 1  # 生产环境建议3节点集群
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management
        ports:
        - containerPort: 5672
          name: amqp
        - containerPort: 15672
          name: management
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secrets
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secrets
              key: password
        volumeMounts:
        - name: data
          mountPath: /var/lib/rabbitmq
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          exec:
            command: ["rabbitmq-diagnostics", "ping"]
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          exec:
            command: ["rabbitmq-diagnostics", "ping"]
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: rabbitmq-pvc
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rabbitmq-pvc
  namespace: voiceassistant-prod
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: standard
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: voiceassistant-prod
spec:
  type: ClusterIP
  ports:
  - port: 5672
    targetPort: 5672
    name: amqp
  - port: 15672
    targetPort: 15672
    name: management
  selector:
    app: rabbitmq
---
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secrets
  namespace: voiceassistant-prod
type: Opaque
stringData:
  username: admin
  password: admin123
```

**部署RabbitMQ**:
```bash
kubectl apply -f deployments/k8s/infrastructure/rabbitmq/

# 等待Pod就绪
kubectl wait --for=condition=ready pod -l app=rabbitmq -n voiceassistant-prod --timeout=300s

# 访问管理界面（端口转发）
kubectl port-forward svc/rabbitmq 15672:15672 -n voiceassistant-prod

# 访问 http://localhost:15672 (admin/admin123)
```

#### Task 1.2: 数据模型设计 (1天)

**Notification模型**:
```go
// cmd/notification-service/internal/model/notification.go
package model

import "time"

type Notification struct {
    ID          string                 `json:"id" gorm:"primaryKey"`
    UserID      string                 `json:"user_id" gorm:"index;not null"`
    TenantID    string                 `json:"tenant_id" gorm:"index"`
    Type        string                 `json:"type" gorm:"not null"` // websocket/email/sms/push
    Channel     string                 `json:"channel"`              // 实际发送渠道
    Title       string                 `json:"title"`
    Content     string                 `json:"content" gorm:"type:text"`
    Data        map[string]interface{} `json:"data" gorm:"type:jsonb"`
    Status      string                 `json:"status" gorm:"index;default:'pending'"` // pending/sent/failed
    ErrorMsg    string                 `json:"error_msg" gorm:"type:text"`
    SentAt      *time.Time             `json:"sent_at"`
    CreatedAt   time.Time              `json:"created_at"`
    UpdatedAt   time.Time              `json:"updated_at"`
}

// 通知类型
const (
    TypeWebSocket = "websocket"
    TypeEmail     = "email"
    TypeSMS       = "sms"
    TypePush      = "push"
)

// 通知状态
const (
    StatusPending = "pending"
    StatusSent    = "sent"
    StatusFailed  = "failed"
)
```

**Template模型**:
```go
// cmd/notification-service/internal/model/template.go
package model

import "time"

type NotificationTemplate struct {
    ID          uint      `json:"id" gorm:"primaryKey"`
    Name        string    `json:"name" gorm:"uniqueIndex;not null"`
    Type        string    `json:"type" gorm:"not null"` // email/sms/websocket
    Title       string    `json:"title"`
    Content     string    `json:"content" gorm:"type:text"`
    Variables   []string  `json:"variables" gorm:"type:jsonb"`
    Description string    `json:"description"`
    CreatedAt   time.Time `json:"created_at"`
    UpdatedAt   time.Time `json:"updated_at"`
}
```

**数据库表**:
```sql
-- 通知记录表
CREATE TABLE notifications (
    id          VARCHAR(100) PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL,
    tenant_id   VARCHAR(100),
    type        VARCHAR(50) NOT NULL,
    channel     VARCHAR(50),
    title       VARCHAR(255),
    content     TEXT,
    data        JSONB,
    status      VARCHAR(20) DEFAULT 'pending',
    error_msg   TEXT,
    sent_at     TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_tenant_id (tenant_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- 通知模板表
CREATE TABLE notification_templates (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    type        VARCHAR(50) NOT NULL,
    title       VARCHAR(255),
    content     TEXT,
    variables   JSONB,
    description TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_name (name),
    INDEX idx_type (type)
);
```

#### Task 1.3: RabbitMQ客户端实现 (2天)

**配置结构**:
```go
// cmd/notification-service/config/config.go
type RabbitMQConfig struct {
    URL      string `mapstructure:"url" default:"amqp://admin:admin123@rabbitmq:5672/"`
    Exchange string `mapstructure:"exchange" default:"notification-exchange"`
    Queues   QueueConfig
}

type QueueConfig struct {
    WebSocket string `mapstructure:"websocket" default:"notification-websocket"`
    Email     string `mapstructure:"email" default:"notification-email"`
    SMS       string `mapstructure:"sms" default:"notification-sms"`
}
```

**RabbitMQ客户端**:
```go
// cmd/notification-service/internal/mq/rabbitmq.go
package mq

import (
    "fmt"

    amqp "github.com/rabbitmq/amqp091-go"
    "github.com/sirupsen/logrus"
)

type RabbitMQClient struct {
    conn     *amqp.Connection
    channel  *amqp.Channel
    exchange string
    logger   *logrus.Logger
}

func NewRabbitMQClient(url, exchange string, logger *logrus.Logger) (*RabbitMQClient, error) {
    // 1. 连接RabbitMQ
    conn, err := amqp.Dial(url)
    if err != nil {
        return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
    }

    // 2. 创建Channel
    channel, err := conn.Channel()
    if err != nil {
        conn.Close()
        return nil, fmt.Errorf("failed to open channel: %w", err)
    }

    // 3. 声明Exchange（Topic类型，支持路由）
    err = channel.ExchangeDeclare(
        exchange,             // name
        amqp.ExchangeTopic,   // type
        true,                 // durable
        false,                // auto-deleted
        false,                // internal
        false,                // no-wait
        nil,                  // arguments
    )
    if err != nil {
        channel.Close()
        conn.Close()
        return nil, fmt.Errorf("failed to declare exchange: %w", err)
    }

    client := &RabbitMQClient{
        conn:     conn,
        channel:  channel,
        exchange: exchange,
        logger:   logger,
    }

    logger.Info("RabbitMQ client initialized")

    return client, nil
}

// DeclareQueue 声明队列
func (c *RabbitMQClient) DeclareQueue(name, routingKey string) error {
    // 1. 声明队列
    _, err := c.channel.QueueDeclare(
        name,  // name
        true,  // durable
        false, // auto-delete
        false, // exclusive
        false, // no-wait
        nil,   // arguments
    )
    if err != nil {
        return err
    }

    // 2. 绑定队列到Exchange
    err = c.channel.QueueBind(
        name,            // queue name
        routingKey,      // routing key
        c.exchange,      // exchange
        false,           // no-wait
        nil,             // arguments
    )

    return err
}

// Publish 发布消息
func (c *RabbitMQClient) Publish(routingKey string, body []byte) error {
    err := c.channel.Publish(
        c.exchange,  // exchange
        routingKey,  // routing key
        false,       // mandatory
        false,       // immediate
        amqp.Publishing{
            ContentType:  "application/json",
            Body:         body,
            DeliveryMode: amqp.Persistent, // 持久化
        },
    )

    if err != nil {
        c.logger.Errorf("Failed to publish message: %v", err)
        return err
    }

    return nil
}

// Consume 消费消息
func (c *RabbitMQClient) Consume(queueName string) (<-chan amqp.Delivery, error) {
    msgs, err := c.channel.Consume(
        queueName, // queue
        "",        // consumer
        false,     // auto-ack
        false,     // exclusive
        false,     // no-local
        false,     // no-wait
        nil,       // args
    )

    return msgs, err
}

// Close 关闭连接
func (c *RabbitMQClient) Close() error {
    if err := c.channel.Close(); err != nil {
        c.logger.Errorf("Failed to close channel: %v", err)
    }

    if err := c.conn.Close(); err != nil {
        c.logger.Errorf("Failed to close connection: %v", err)
        return err
    }

    return nil
}
```

#### Task 1.4: Notification Service实现 (1天)

**NotificationService**:
```go
// cmd/notification-service/internal/service/notification_service.go
package service

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    "github.com/google/uuid"
    "github.com/sirupsen/logrus"
    "gorm.io/gorm"

    "voiceassistant/cmd/notification-service/internal/model"
    "voiceassistant/cmd/notification-service/internal/mq"
)

type NotificationService struct {
    db              *gorm.DB
    mqClient        *mq.RabbitMQClient
    dedupeService   *DedupeService
    templateService *TemplateService
    logger          *logrus.Logger
}

func NewNotificationService(
    db *gorm.DB,
    mqClient *mq.RabbitMQClient,
    dedupeService *DedupeService,
    templateService *TemplateService,
    logger *logrus.Logger,
) *NotificationService {
    return &NotificationService{
        db:              db,
        mqClient:        mqClient,
        dedupeService:   dedupeService,
        templateService: templateService,
        logger:          logger,
    }
}

// SendNotification 发送通知
func (s *NotificationService) SendNotification(
    ctx context.Context,
    userID, notifType, title, content string,
    data map[string]interface{},
) error {
    // 1. 去重检查
    if s.dedupeService != nil {
        isDuplicate, err := s.dedupeService.IsDuplicate(ctx, userID, notifType, content)
        if err != nil {
            s.logger.Warnf("Dedupe check failed: %v", err)
        } else if isDuplicate {
            s.logger.WithFields(logrus.Fields{
                "user_id": userID,
                "type":    notifType,
            }).Info("Duplicate notification, skipping")
            return nil
        }
    }

    // 2. 创建通知记录
    notification := &model.Notification{
        ID:        uuid.New().String(),
        UserID:    userID,
        Type:      notifType,
        Title:     title,
        Content:   content,
        Data:      data,
        Status:    model.StatusPending,
        CreatedAt: time.Now(),
        UpdatedAt: time.Now(),
    }

    if err := s.db.WithContext(ctx).Create(notification).Error; err != nil {
        return fmt.Errorf("failed to create notification: %w", err)
    }

    // 3. 发布到RabbitMQ
    routingKey := fmt.Sprintf("notification.%s", notifType)
    msgBytes, _ := json.Marshal(notification)

    if err := s.mqClient.Publish(routingKey, msgBytes); err != nil {
        // 更新状态为失败
        s.db.Model(notification).Updates(map[string]interface{}{
            "status":    model.StatusFailed,
            "error_msg": err.Error(),
        })
        return err
    }

    s.logger.WithFields(logrus.Fields{
        "notification_id": notification.ID,
        "user_id":         userID,
        "type":            notifType,
    }).Info("Notification published")

    return nil
}

// SendFromTemplate 使用模板发送通知
func (s *NotificationService) SendFromTemplate(
    ctx context.Context,
    userID, templateName string,
    variables map[string]interface{},
) error {
    // 1. 获取模板
    template, err := s.templateService.GetTemplate(ctx, templateName)
    if err != nil {
        return fmt.Errorf("failed to get template: %w", err)
    }

    // 2. 渲染模板
    title, err := s.templateService.RenderTemplate(template.Title, variables)
    if err != nil {
        return err
    }

    content, err := s.templateService.RenderTemplate(template.Content, variables)
    if err != nil {
        return err
    }

    // 3. 发送通知
    return s.SendNotification(ctx, userID, template.Type, title, content, nil)
}

// UpdateStatus 更新通知状态
func (s *NotificationService) UpdateStatus(
    ctx context.Context,
    notificationID, status, errorMsg string,
) error {
    updates := map[string]interface{}{
        "status":     status,
        "updated_at": time.Now(),
    }

    if status == model.StatusSent {
        now := time.Now()
        updates["sent_at"] = &now
    }

    if errorMsg != "" {
        updates["error_msg"] = errorMsg
    }

    return s.db.WithContext(ctx).
        Model(&model.Notification{}).
        Where("id = ?", notificationID).
        Updates(updates).Error
}
```

**交付物**:
- ✅ RabbitMQ Kubernetes部署文件
- ✅ RabbitMQ客户端实现
- ✅ NotificationService实现
- ✅ 数据模型和表结构
- ✅ 单元测试

---

### Week 2: 通知渠道实现（5天）

#### Task 2.1: WebSocket推送 (1天)

**WebSocket Channel**:
```go
// cmd/notification-service/internal/channel/websocket_channel.go
package channel

import (
    "context"
    "encoding/json"

    "github.com/sirupsen/logrus"

    "voiceassistant/cmd/notification-service/internal/model"
    ws "voiceassistant/cmd/conversation-service/internal/websocket"
)

type WebSocketChannel struct {
    hub    *ws.Hub
    logger *logrus.Logger
}

func NewWebSocketChannel(hub *ws.Hub, logger *logrus.Logger) *WebSocketChannel {
    return &WebSocketChannel{
        hub:    hub,
        logger: logger,
    }
}

// Send 发送WebSocket通知
func (c *WebSocketChannel) Send(ctx context.Context, notification *model.Notification) error {
    // 构建WebSocket消息
    message := map[string]interface{}{
        "type":            "notification",
        "notification_id": notification.ID,
        "title":           notification.Title,
        "content":         notification.Content,
        "data":            notification.Data,
        "timestamp":       notification.CreatedAt.Unix(),
    }

    msgBytes, err := json.Marshal(message)
    if err != nil {
        return err
    }

    // 广播给用户的所有设备
    c.hub.Broadcast <- &ws.BroadcastMessage{
        UserID:  notification.UserID,
        Message: msgBytes,
    }

    c.logger.WithFields(logrus.Fields{
        "notification_id": notification.ID,
        "user_id":         notification.UserID,
    }).Info("WebSocket notification sent")

    return nil
}
```

**WebSocket Worker**:
```go
// cmd/notification-service/internal/worker/websocket_worker.go
package worker

import (
    "context"
    "encoding/json"

    amqp "github.com/rabbitmq/amqp091-go"
    "github.com/sirupsen/logrus"

    "voiceassistant/cmd/notification-service/internal/channel"
    "voiceassistant/cmd/notification-service/internal/model"
    "voiceassistant/cmd/notification-service/internal/service"
)

type WebSocketWorker struct {
    channel           *channel.WebSocketChannel
    notificationService *service.NotificationService
    logger            *logrus.Logger
}

func NewWebSocketWorker(
    channel *channel.WebSocketChannel,
    notificationService *service.NotificationService,
    logger *logrus.Logger,
) *WebSocketWorker {
    return &WebSocketWorker{
        channel:           channel,
        notificationService: notificationService,
        logger:            logger,
    }
}

// ProcessMessages 处理消息
func (w *WebSocketWorker) ProcessMessages(msgs <-chan amqp.Delivery) {
    for msg := range msgs {
        w.processMessage(msg)
    }
}

// processMessage 处理单条消息
func (w *WebSocketWorker) processMessage(msg amqp.Delivery) {
    ctx := context.Background()

    // 1. 解析消息
    var notification model.Notification
    if err := json.Unmarshal(msg.Body, &notification); err != nil {
        w.logger.Errorf("Failed to unmarshal notification: %v", err)
        msg.Nack(false, false) // 不重新入队
        return
    }

    // 2. 发送WebSocket通知
    if err := w.channel.Send(ctx, &notification); err != nil {
        w.logger.Errorf("Failed to send WebSocket notification: %v", err)

        // 更新状态为失败
        w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusFailed, err.Error())

        msg.Nack(false, true) // 重新入队
        return
    }

    // 3. 更新状态为已发送
    if err := w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusSent, ""); err != nil {
        w.logger.Warnf("Failed to update notification status: %v", err)
    }

    // 4. 确认消息
    msg.Ack(false)
}
```

#### Task 2.2: 邮件通知 (2天)

**Email Channel**:
```go
// cmd/notification-service/internal/channel/email_channel.go
package channel

import (
    "context"
    "fmt"

    "github.com/sirupsen/logrus"
    "gopkg.in/gomail.v2"

    "voiceassistant/cmd/notification-service/internal/model"
)

type EmailChannel struct {
    smtpHost     string
    smtpPort     int
    smtpUser     string
    smtpPassword string
    fromAddr     string
    fromName     string
    logger       *logrus.Logger
}

type EmailConfig struct {
    SMTPHost     string
    SMTPPort     int
    SMTPUser     string
    SMTPPassword string
    FromAddr     string
    FromName     string
}

func NewEmailChannel(config *EmailConfig, logger *logrus.Logger) *EmailChannel {
    return &EmailChannel{
        smtpHost:     config.SMTPHost,
        smtpPort:     config.SMTPPort,
        smtpUser:     config.SMTPUser,
        smtpPassword: config.SMTPPassword,
        fromAddr:     config.FromAddr,
        fromName:     config.FromName,
        logger:       logger,
    }
}

// Send 发送邮件
func (c *EmailChannel) Send(ctx context.Context, notification *model.Notification, toAddr string) error {
    // 1. 创建邮件
    m := gomail.NewMessage()

    // From
    m.SetHeader("From", m.FormatAddress(c.fromAddr, c.fromName))

    // To
    m.SetHeader("To", toAddr)

    // Subject
    m.SetHeader("Subject", notification.Title)

    // Body
    m.SetBody("text/html", notification.Content)

    // 2. 创建Dialer
    d := gomail.NewDialer(c.smtpHost, c.smtpPort, c.smtpUser, c.smtpPassword)

    // 3. 发送邮件
    if err := d.DialAndSend(m); err != nil {
        return fmt.Errorf("failed to send email: %w", err)
    }

    c.logger.WithFields(logrus.Fields{
        "notification_id": notification.ID,
        "to":              toAddr,
    }).Info("Email sent")

    return nil
}
```

**Email Worker**:
```go
// cmd/notification-service/internal/worker/email_worker.go
package worker

import (
    "context"
    "encoding/json"

    amqp "github.com/rabbitmq/amqp091-go"
    "github.com/sirupsen/logrus"
    "gorm.io/gorm"

    "voiceassistant/cmd/notification-service/internal/channel"
    "voiceassistant/cmd/notification-service/internal/model"
    "voiceassistant/cmd/notification-service/internal/service"
)

type EmailWorker struct {
    channel             *channel.EmailChannel
    notificationService *service.NotificationService
    db                  *gorm.DB
    logger              *logrus.Logger
}

func NewEmailWorker(
    channel *channel.EmailChannel,
    notificationService *service.NotificationService,
    db *gorm.DB,
    logger *logrus.Logger,
) *EmailWorker {
    return &EmailWorker{
        channel:             channel,
        notificationService: notificationService,
        db:                  db,
        logger:              logger,
    }
}

// ProcessMessages 处理消息
func (w *EmailWorker) ProcessMessages(msgs <-chan amqp.Delivery) {
    for msg := range msgs {
        w.processMessage(msg)
    }
}

// processMessage 处理单条消息
func (w *EmailWorker) processMessage(msg amqp.Delivery) {
    ctx := context.Background()

    // 1. 解析消息
    var notification model.Notification
    if err := json.Unmarshal(msg.Body, &notification); err != nil {
        w.logger.Errorf("Failed to unmarshal notification: %v", err)
        msg.Nack(false, false)
        return
    }

    // 2. 获取用户邮箱
    var user struct {
        Email string
    }
    if err := w.db.Table("users").Where("id = ?", notification.UserID).First(&user).Error; err != nil {
        w.logger.Errorf("Failed to get user email: %v", err)
        w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusFailed, "User not found")
        msg.Ack(false)
        return
    }

    if user.Email == "" {
        w.logger.Warn("User has no email address")
        w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusFailed, "No email address")
        msg.Ack(false)
        return
    }

    // 3. 发送邮件
    if err := w.channel.Send(ctx, &notification, user.Email); err != nil {
        w.logger.Errorf("Failed to send email: %v", err)
        w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusFailed, err.Error())
        msg.Nack(false, true) // 重新入队
        return
    }

    // 4. 更新状态
    w.notificationService.UpdateStatus(ctx, notification.ID, model.StatusSent, "")
    msg.Ack(false)
}
```

#### Task 2.3: 短信通知（可选）(1天)

**SMS Channel（阿里云示例）**:
```go
// cmd/notification-service/internal/channel/sms_channel.go
package channel

import (
    "context"
    "fmt"

    "github.com/aliyun/alibaba-cloud-sdk-go/services/dysmsapi"
    "github.com/sirupsen/logrus"

    "voiceassistant/cmd/notification-service/internal/model"
)

type SMSChannel struct {
    client       *dysmsapi.Client
    signName     string
    templateCode string
    logger       *logrus.Logger
}

type SMSConfig struct {
    AccessKeyID     string
    AccessKeySecret string
    RegionID        string
    SignName        string
    TemplateCode    string
}

func NewSMSChannel(config *SMSConfig, logger *logrus.Logger) (*SMSChannel, error) {
    client, err := dysmsapi.NewClientWithAccessKey(
        config.RegionID,
        config.AccessKeyID,
        config.AccessKeySecret,
    )
    if err != nil {
        return nil, err
    }

    return &SMSChannel{
        client:       client,
        signName:     config.SignName,
        templateCode: config.TemplateCode,
        logger:       logger,
    }, nil
}

// Send 发送短信
func (c *SMSChannel) Send(ctx context.Context, notification *model.Notification, phoneNumber string) error {
    request := dysmsapi.CreateSendSmsRequest()
    request.Scheme = "https"

    request.PhoneNumbers = phoneNumber
    request.SignName = c.signName
    request.TemplateCode = c.templateCode
    request.TemplateParam = fmt.Sprintf(`{"content":"%s"}`, notification.Content)

    response, err := c.client.SendSms(request)
    if err != nil {
        return fmt.Errorf("failed to send SMS: %w", err)
    }

    if response.Code != "OK" {
        return fmt.Errorf("SMS send failed: %s - %s", response.Code, response.Message)
    }

    c.logger.WithFields(logrus.Fields{
        "notification_id": notification.ID,
        "phone":           phoneNumber,
    }).Info("SMS sent")

    return nil
}
```

#### Task 2.4: 通知模板系统 (1天)

**TemplateService**:
```go
// cmd/notification-service/internal/service/template_service.go
package service

import (
    "bytes"
    "context"
    "fmt"
    "text/template"

    "github.com/sirupsen/logrus"
    "gorm.io/gorm"

    "voiceassistant/cmd/notification-service/internal/model"
)

type TemplateService struct {
    db     *gorm.DB
    logger *logrus.Logger
}

func NewTemplateService(db *gorm.DB, logger *logrus.Logger) *TemplateService {
    return &TemplateService{
        db:     db,
        logger: logger,
    }
}

// GetTemplate 获取模板
func (s *TemplateService) GetTemplate(ctx context.Context, name string) (*model.NotificationTemplate, error) {
    var tmpl model.NotificationTemplate
    if err := s.db.WithContext(ctx).Where("name = ?", name).First(&tmpl).Error; err != nil {
        return nil, err
    }

    return &tmpl, nil
}

// RenderTemplate 渲染模板
func (s *TemplateService) RenderTemplate(tmplStr string, variables map[string]interface{}) (string, error) {
    tmpl, err := template.New("notification").Parse(tmplStr)
    if err != nil {
        return "", fmt.Errorf("failed to parse template: %w", err)
    }

    var buf bytes.Buffer
    if err := tmpl.Execute(&buf, variables); err != nil {
        return "", fmt.Errorf("failed to execute template: %w", err)
    }

    return buf.String(), nil
}

// CreateTemplate 创建模板
func (s *TemplateService) CreateTemplate(
    ctx context.Context,
    name, notifType, title, content, description string,
    variables []string,
) error {
    tmpl := &model.NotificationTemplate{
        Name:        name,
        Type:        notifType,
        Title:       title,
        Content:     content,
        Variables:   variables,
        Description: description,
    }

    return s.db.WithContext(ctx).Create(tmpl).Error
}
```

**预置模板（初始化）**:
```sql
-- 插入默认模板
INSERT INTO notification_templates (name, type, title, content, variables, description) VALUES
('welcome_email', 'email',
 'Welcome to VoiceAssistant',
 '<h1>Hi {{.Username}},</h1><p>Welcome to VoiceAssistant! Your account has been created successfully.</p>',
 '["Username"]',
 'Welcome email for new users'),

('password_changed', 'email',
 'Password Changed',
 '<p>Hi {{.Username}},</p><p>Your password was changed at {{.Timestamp}}. If you did not make this change, please contact support.</p>',
 '["Username", "Timestamp"]',
 'Password change notification'),

('message_received', 'websocket',
 'New Message',
 '{{.SenderName}} sent you a message: {{.Content}}',
 '["SenderName", "Content"]',
 'New message notification');
```

**交付物**:
- ✅ WebSocket Channel & Worker
- ✅ Email Channel & Worker
- ✅ SMS Channel & Worker（可选）
- ✅ TemplateService实现
- ✅ 预置模板
- ✅ 单元测试

---

### Week 3: 去重机制与测试（5天）

#### Task 3.1: 通知去重 (2天)

**DedupeService**:
```go
// cmd/notification-service/internal/service/dedupe_service.go
package service

import (
    "context"
    "crypto/sha256"
    "fmt"
    "time"

    "github.com/redis/go-redis/v9"
    "github.com/sirupsen/logrus"
)

type DedupeService struct {
    redis  *redis.Client
    ttl    time.Duration
    logger *logrus.Logger
}

func NewDedupeService(redis *redis.Client, logger *logrus.Logger) *DedupeService {
    return &DedupeService{
        redis:  redis,
        ttl:    5 * time.Minute, // 5分钟内的重复通知会被过滤
        logger: logger,
    }
}

// IsDuplicate 检查是否为重复通知
func (d *DedupeService) IsDuplicate(
    ctx context.Context,
    userID, notifType, content string,
) (bool, error) {
    // 1. 生成去重Key
    key := d.generateKey(userID, notifType, content)

    // 2. 检查Redis
    exists, err := d.redis.Exists(ctx, key).Result()
    if err != nil {
        return false, err
    }

    if exists > 0 {
        return true, nil
    }

    // 3. 设置Key（标记为已发送）
    if err := d.redis.Set(ctx, key, "1", d.ttl).Err(); err != nil {
        d.logger.Warnf("Failed to set dedupe key: %v", err)
    }

    return false, nil
}

// generateKey 生成去重Key
func (d *DedupeService) generateKey(userID, notifType, content string) string {
    // 使用SHA256生成唯一Key
    h := sha256.New()
    h.Write([]byte(fmt.Sprintf("%s:%s:%s", userID, notifType, content)))
    hash := fmt.Sprintf("%x", h.Sum(nil))

    return fmt.Sprintf("notif:dedupe:%s", hash)
}
```

#### Task 3.2: 集成测试 (2天)

**完整流程测试**:
```go
// tests/integration/notification_test.go
package integration_test

import (
    "context"
    "testing"
    "time"

    "github.com/stretchr/testify/assert"

    "voiceassistant/cmd/notification-service/internal/service"
)

func TestNotificationWorkflow_E2E(t *testing.T) {
    // 1. 发送通知
    err := notificationService.SendNotification(
        context.Background(),
        "user123",
        "email",
        "Test Notification",
        "This is a test",
        nil,
    )
    assert.NoError(t, err)

    // 2. 等待处理
    time.Sleep(2 * time.Second)

    // 3. 验证通知状态
    // TODO: 查询数据库验证
}
```

#### Task 3.3: 性能测试与优化 (1天)

**性能测试**:
```bash
# 使用Apache Bench测试
ab -n 10000 -c 100 http://localhost:9004/api/v1/notifications
```

**监控指标**:
```go
// internal/metrics/notification_metrics.go
var (
    NotificationsSent = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "notifications_sent_total",
        Help: "Total number of notifications sent",
    }, []string{"type", "status"})

    NotificationDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
        Name: "notification_duration_seconds",
        Help: "Notification processing duration",
    }, []string{"type"})
)
```

**交付物**:
- ✅ DedupeService实现
- ✅ 集成测试
- ✅ 性能测试
- ✅ Prometheus指标
- ✅ 文档更新

---

## 📊 验收标准

### 功能验收

| 功能 | 验收标准 | 验收方法 |
|-----|---------|---------|
| RabbitMQ集成 | 消息可靠传递 | 手动测试 |
| WebSocket推送 | 实时推送<100ms | 压测 |
| 邮件发送 | 成功率>99% | 集成测试 |
| 通知模板 | 模板正确渲染 | 单元测试 |
| 通知去重 | 重复通知被过滤 | 集成测试 |

### 性能验收

| 指标 | 目标 | 实际 | 验收方法 |
|-----|------|------|---------|
| 消息吞吐量 | 1000/s | TBD | 压测 |
| WebSocket延迟 | <100ms | TBD | 压测 |
| 邮件发送延迟 | <5s | TBD | 集成测试 |
| 去重查询延迟 | <10ms | TBD | 单元测试 |

---

## 📖 相关文档

- [VoiceHelper-05-NotificationService.md](../VoiceHelper-05-NotificationService.md)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)

---

**文档版本**: v1.0
**最后更新**: 2025-01-27
**维护者**: VoiceAssistant后端团队
