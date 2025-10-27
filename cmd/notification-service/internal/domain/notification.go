package domain

import "time"

// Notification 通知领域模型
type Notification struct {
	ID        string
	TenantID  string
	UserID    string
	Channel   string // email, sms, websocket, webhook
	Priority  string // low, medium, high, critical
	Title     string
	Content   string
	Status    string // pending, sending, sent, failed
	SentAt    *time.Time
	ReadAt    *time.Time
	Metadata  map[string]string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// NotificationRepository 通知仓储接口
type NotificationRepository interface {
	Create(notification *Notification) error
	Update(notification *Notification) error
	GetByID(id string) (*Notification, error)
	GetByUserID(userID string, limit, offset int) ([]*Notification, error)
	GetUnreadCount(userID string) (int64, error)
	Delete(id string) error
}

// Template 通知模板
type Template struct {
	ID        string
	TenantID  string
	Name      string
	Title     string
	Content   string
	Channel   string
	Variables []string // 模板变量列表
	IsActive  bool
	CreatedAt time.Time
	UpdatedAt time.Time
}

// TemplateRepository 模板仓储接口
type TemplateRepository interface {
	Create(template *Template) error
	Update(template *Template) error
	GetByID(id string) (*Template, error)
	GetByTenantID(tenantID string) ([]*Template, error)
	Delete(id string) error
}
