package domain

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/google/uuid"
)

// NotificationChannel 通知渠道
type NotificationChannel string

const (
	ChannelEmail     NotificationChannel = "email"
	ChannelSMS       NotificationChannel = "sms"
	ChannelWebSocket NotificationChannel = "websocket"
	ChannelWebhook   NotificationChannel = "webhook"
	ChannelInApp     NotificationChannel = "inapp"
)

// NotificationStatus 通知状态
type NotificationStatus string

const (
	StatusPending  NotificationStatus = "pending"
	StatusSending  NotificationStatus = "sending"
	StatusSent     NotificationStatus = "sent"
	StatusFailed   NotificationStatus = "failed"
	StatusRetrying NotificationStatus = "retrying"
)

// NotificationPriority 通知优先级
type NotificationPriority string

const (
	PriorityLow      NotificationPriority = "low"
	PriorityMedium   NotificationPriority = "medium"
	PriorityHigh     NotificationPriority = "high"
	PriorityCritical NotificationPriority = "critical"
)

// Notification 通知领域模型
type Notification struct {
	ID        string                   `json:"id" gorm:"primaryKey"`
	TenantID  string                   `json:"tenant_id" gorm:"index:idx_tenant_user"`
	UserID    string                   `json:"user_id" gorm:"index:idx_tenant_user;index:idx_user_status"`
	Channel   NotificationChannel      `json:"channel" gorm:"index"`
	Priority  NotificationPriority     `json:"priority"`
	Title     string                   `json:"title"`
	Content   string                   `json:"content" gorm:"type:text"`
	Status    NotificationStatus       `json:"status" gorm:"index:idx_user_status"`
	Recipient string                   `json:"recipient"` // email address, phone number, etc.
	SentAt    *time.Time               `json:"sent_at,omitempty"`
	ReadAt    *time.Time               `json:"read_at,omitempty"`
	Metadata  MetadataMap              `json:"metadata,omitempty" gorm:"type:jsonb"`
	ErrorMsg  string                   `json:"error_msg,omitempty"`
	Attempts  int                      `json:"attempts" gorm:"default:0"`
	CreatedAt time.Time                `json:"created_at" gorm:"index"`
	UpdatedAt time.Time                `json:"updated_at"`
}

// MetadataMap is a custom type for JSONB storage
type MetadataMap map[string]interface{}

// Scan implements sql.Scanner interface
func (m *MetadataMap) Scan(value interface{}) error {
	if value == nil {
		*m = make(map[string]interface{})
		return nil
	}
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("failed to unmarshal JSONB value")
	}
	return json.Unmarshal(bytes, m)
}

// Value implements driver.Valuer interface
func (m MetadataMap) Value() (interface{}, error) {
	if m == nil {
		return nil, nil
	}
	return json.Marshal(m)
}

// TableName specifies the table name
func (Notification) TableName() string {
	return "notifications"
}

// NewNotification creates a new notification
func NewNotification(
	tenantID, userID, recipient string,
	channel NotificationChannel,
	priority NotificationPriority,
	title, content string,
) *Notification {
	return &Notification{
		ID:        uuid.New().String(),
		TenantID:  tenantID,
		UserID:    userID,
		Recipient: recipient,
		Channel:   channel,
		Priority:  priority,
		Title:     title,
		Content:   content,
		Status:    StatusPending,
		Metadata:  make(MetadataMap),
		Attempts:  0,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}
}

// Validate validates the notification
func (n *Notification) Validate() error {
	if n.TenantID == "" {
		return errors.New("tenant_id is required")
	}
	if n.UserID == "" {
		return errors.New("user_id is required")
	}
	if n.Recipient == "" {
		return errors.New("recipient is required")
	}
	if n.Title == "" && n.Content == "" {
		return errors.New("title or content is required")
	}
	if !n.isValidChannel() {
		return errors.New("invalid channel")
	}
	return nil
}

// isValidChannel checks if channel is valid
func (n *Notification) isValidChannel() bool {
	validChannels := []NotificationChannel{
		ChannelEmail, ChannelSMS, ChannelWebSocket, ChannelWebhook, ChannelInApp,
	}
	for _, ch := range validChannels {
		if n.Channel == ch {
			return true
		}
	}
	return false
}

// MarkAsSent marks the notification as sent
func (n *Notification) MarkAsSent() {
	now := time.Now()
	n.Status = StatusSent
	n.SentAt = &now
	n.UpdatedAt = now
}

// MarkAsFailed marks the notification as failed
func (n *Notification) MarkAsFailed(err error) {
	n.Status = StatusFailed
	n.ErrorMsg = err.Error()
	n.UpdatedAt = time.Now()
}

// MarkAsRead marks the notification as read
func (n *Notification) MarkAsRead() {
	now := time.Now()
	n.ReadAt = &now
	n.UpdatedAt = now
}

// IncrementAttempts increments the retry attempts
func (n *Notification) IncrementAttempts() {
	n.Attempts++
	n.UpdatedAt = time.Now()
}

// NotificationRepository 通知仓储接口
type NotificationRepository interface {
	Create(ctx context.Context, notification *Notification) error
	Update(ctx context.Context, notification *Notification) error
	GetByID(ctx context.Context, id string) (*Notification, error)
	GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*Notification, error)
	GetUnreadCount(ctx context.Context, userID string) (int64, error)
	Delete(ctx context.Context, id string) error
	List(ctx context.Context, userID, tenantID string, status *NotificationStatus, page, pageSize int) ([]*Notification, int64, error)
}

// TemplateType 模板类型
type TemplateType string

const (
	TemplateEmail     TemplateType = "email"
	TemplateSMS       TemplateType = "sms"
	TemplateWebSocket TemplateType = "websocket"
	TemplateInApp     TemplateType = "inapp"
)

// Template 通知模板
type Template struct {
	ID          string       `json:"id" gorm:"primaryKey"`
	TenantID    string       `json:"tenant_id" gorm:"index:idx_tenant_name,unique"`
	Name        string       `json:"name" gorm:"index:idx_tenant_name,unique"`
	Type        TemplateType `json:"type"`
	Title       string       `json:"title"`
	Content     string       `json:"content" gorm:"type:text"`
	Description string       `json:"description"`
	Variables   []string     `json:"variables" gorm:"type:jsonb"` // 模板变量列表
	IsActive    bool         `json:"is_active" gorm:"default:true"`
	CreatedAt   time.Time    `json:"created_at"`
	UpdatedAt   time.Time    `json:"updated_at"`
}

// TableName specifies the table name
func (Template) TableName() string {
	return "notification_templates"
}

// NewTemplate creates a new template
func NewTemplate(name string, templateType TemplateType, tenantID, title, content string) *Template {
	return &Template{
		ID:        uuid.New().String(),
		TenantID:  tenantID,
		Name:      name,
		Type:      templateType,
		Title:     title,
		Content:   content,
		IsActive:  true,
		Variables: []string{},
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}
}

// Validate validates the template
func (t *Template) Validate() error {
	if t.TenantID == "" {
		return errors.New("tenant_id is required")
	}
	if t.Name == "" {
		return errors.New("name is required")
	}
	if t.Title == "" && t.Content == "" {
		return errors.New("title or content is required")
	}
	return nil
}

// Update updates template fields
func (t *Template) Update(title, content, description string) {
	if title != "" {
		t.Title = title
	}
	if content != "" {
		t.Content = content
	}
	if description != "" {
		t.Description = description
	}
	t.UpdatedAt = time.Now()
}

// TemplateRepository 模板仓储接口
type TemplateRepository interface {
	Create(ctx context.Context, template *Template) error
	Update(ctx context.Context, template *Template) error
	GetByID(ctx context.Context, id string) (*Template, error)
	GetByTenantID(ctx context.Context, tenantID string) ([]*Template, error)
	ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*Template, int64, error)
	Delete(ctx context.Context, id string) error
}
