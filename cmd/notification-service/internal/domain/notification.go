package domain

import (
	"time"

	"github.com/google/uuid"
)

// NotificationChannel 通知渠道
type NotificationChannel string

const (
	ChannelEmail   NotificationChannel = "email"   // 邮件
	ChannelSMS     NotificationChannel = "sms"     // 短信
	ChannelPush    NotificationChannel = "push"    // 推送
	ChannelWebhook NotificationChannel = "webhook" // Webhook
	ChannelInApp   NotificationChannel = "in_app"  // 应用内
	ChannelSlack   NotificationChannel = "slack"   // Slack
	ChannelWechat  NotificationChannel = "wechat"  // 微信
)

// NotificationPriority 通知优先级
type NotificationPriority string

const (
	PriorityLow    NotificationPriority = "low"    // 低
	PriorityNormal NotificationPriority = "normal" // 普通
	PriorityHigh   NotificationPriority = "high"   // 高
	PriorityUrgent NotificationPriority = "urgent" // 紧急
)

// NotificationStatus 通知状态
type NotificationStatus string

const (
	StatusPending   NotificationStatus = "pending"   // 待发送
	StatusSending   NotificationStatus = "sending"   // 发送中
	StatusSent      NotificationStatus = "sent"      // 已发送
	StatusDelivered NotificationStatus = "delivered" // 已送达
	StatusFailed    NotificationStatus = "failed"    // 失败
	StatusCancelled NotificationStatus = "cancelled" // 已取消
)

// Notification 通知聚合根
type Notification struct {
	ID          string
	Channel     NotificationChannel
	Priority    NotificationPriority
	Status      NotificationStatus
	TenantID    string
	UserID      string
	TemplateID  string
	Subject     string
	Content     string
	Recipient   string // 收件人（邮箱、手机号等）
	Metadata    map[string]interface{}
	ScheduledAt *time.Time // 计划发送时间
	SentAt      *time.Time // 实际发送时间
	DeliveredAt *time.Time // 送达时间
	ErrorMsg    string
	RetryCount  int
	MaxRetries  int
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// NewNotification 创建新通知
func NewNotification(
	channel NotificationChannel,
	tenantID, userID string,
	recipient string,
) *Notification {
	id := "notif_" + uuid.New().String()
	now := time.Now()

	return &Notification{
		ID:         id,
		Channel:    channel,
		Priority:   PriorityNormal,
		Status:     StatusPending,
		TenantID:   tenantID,
		UserID:     userID,
		Recipient:  recipient,
		Metadata:   make(map[string]interface{}),
		RetryCount: 0,
		MaxRetries: 3,
		CreatedAt:  now,
		UpdatedAt:  now,
	}
}

// SetContent 设置内容
func (n *Notification) SetContent(subject, content string) {
	n.Subject = subject
	n.Content = content
	n.UpdatedAt = time.Now()
}

// SetTemplate 设置模板
func (n *Notification) SetTemplate(templateID string) {
	n.TemplateID = templateID
	n.UpdatedAt = time.Now()
}

// SetPriority 设置优先级
func (n *Notification) SetPriority(priority NotificationPriority) {
	n.Priority = priority
	n.UpdatedAt = time.Now()
}

// Schedule 计划发送
func (n *Notification) Schedule(scheduledAt time.Time) {
	n.ScheduledAt = &scheduledAt
	n.UpdatedAt = time.Now()
}

// StartSending 开始发送
func (n *Notification) StartSending() {
	n.Status = StatusSending
	now := time.Now()
	n.SentAt = &now
	n.UpdatedAt = now
}

// MarkSent 标记已发送
func (n *Notification) MarkSent() {
	n.Status = StatusSent
	if n.SentAt == nil {
		now := time.Now()
		n.SentAt = &now
	}
	n.UpdatedAt = time.Now()
}

// MarkDelivered 标记已送达
func (n *Notification) MarkDelivered() {
	n.Status = StatusDelivered
	now := time.Now()
	n.DeliveredAt = &now
	n.UpdatedAt = now
}

// MarkFailed 标记失败
func (n *Notification) MarkFailed(errorMsg string) {
	n.Status = StatusFailed
	n.ErrorMsg = errorMsg
	n.UpdatedAt = time.Now()
}

// IncrementRetry 增加重试次数
func (n *Notification) IncrementRetry() {
	n.RetryCount++
	n.UpdatedAt = time.Now()
}

// Cancel 取消通知
func (n *Notification) Cancel() {
	n.Status = StatusCancelled
	n.UpdatedAt = time.Now()
}

// CanRetry 检查是否可以重试
func (n *Notification) CanRetry() bool {
	return n.Status == StatusFailed && n.RetryCount < n.MaxRetries
}

// IsPending 检查是否待发送
func (n *Notification) IsPending() bool {
	return n.Status == StatusPending
}

// IsScheduled 检查是否计划发送
func (n *Notification) IsScheduled() bool {
	if n.ScheduledAt == nil {
		return false
	}
	return n.ScheduledAt.After(time.Now())
}

// ShouldSend 检查是否应该发送
func (n *Notification) ShouldSend() bool {
	if !n.IsPending() {
		return false
	}
	if n.ScheduledAt == nil {
		return true
	}
	return n.ScheduledAt.Before(time.Now()) || n.ScheduledAt.Equal(time.Now())
}

// UpdateMetadata 更新元数据
func (n *Notification) UpdateMetadata(key string, value interface{}) {
	if n.Metadata == nil {
		n.Metadata = make(map[string]interface{})
	}
	n.Metadata[key] = value
	n.UpdatedAt = time.Now()
}

// Validate 验证通知
func (n *Notification) Validate() error {
	if n.Recipient == "" {
		return ErrInvalidRecipient
	}
	if n.Content == "" && n.TemplateID == "" {
		return ErrMissingContent
	}
	return nil
}
