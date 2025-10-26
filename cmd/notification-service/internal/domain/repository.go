package domain

import (
	"context"
	"time"
)

// NotificationRepository 通知仓储接口
type NotificationRepository interface {
	// Create 创建通知
	Create(ctx context.Context, notification *Notification) error

	// GetByID 根据ID获取通知
	GetByID(ctx context.Context, id string) (*Notification, error)

	// Update 更新通知
	Update(ctx context.Context, notification *Notification) error

	// ListByUser 获取用户的通知列表
	ListByUser(ctx context.Context, userID string, offset, limit int) ([]*Notification, int64, error)

	// ListByStatus 根据状态获取通知列表
	ListByStatus(ctx context.Context, status NotificationStatus, limit int) ([]*Notification, error)

	// ListPending 获取待发送通知列表
	ListPending(ctx context.Context, limit int) ([]*Notification, error)

	// ListScheduled 获取计划发送通知列表
	ListScheduled(ctx context.Context, beforeTime time.Time, limit int) ([]*Notification, error)

	// CountByStatus 统计状态数量
	CountByStatus(ctx context.Context, status NotificationStatus) (int64, error)
}

// TemplateRepository 模板仓储接口
type TemplateRepository interface {
	// Create 创建模板
	Create(ctx context.Context, template *Template) error

	// GetByID 根据ID获取模板
	GetByID(ctx context.Context, id string) (*Template, error)

	// GetByName 根据名称获取模板
	GetByName(ctx context.Context, tenantID, name string) (*Template, error)

	// Update 更新模板
	Update(ctx context.Context, template *Template) error

	// Delete 删除模板
	Delete(ctx context.Context, id string) error

	// ListByTenant 获取租户的模板列表
	ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*Template, int64, error)

	// ListByType 根据类型获取模板列表
	ListByType(ctx context.Context, templateType TemplateType) ([]*Template, error)

	// ListActive 获取激活的模板列表
	ListActive(ctx context.Context, tenantID string) ([]*Template, error)
}

// NotificationProvider 通知发送提供商接口
type NotificationProvider interface {
	// Send 发送通知
	Send(ctx context.Context, notification *Notification) error

	// GetChannel 获取支持的渠道
	GetChannel() NotificationChannel

	// IsAvailable 检查是否可用
	IsAvailable() bool
}
