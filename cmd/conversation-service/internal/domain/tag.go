package domain

import (
	"context"
	"time"
)

// Tag 标签
type Tag struct {
	ID          string
	TenantID    string
	Name        string
	Color       string // 标签颜色
	Description string
	UsageCount  int // 使用次数
	CreatedBy   string
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// ConversationTag 对话标签关联
type ConversationTag struct {
	ConversationID string
	TagID          string
	CreatedAt      time.Time
}

// Category 分类
type Category struct {
	ID          string
	TenantID    string
	Name        string
	Description string
	ParentID    *string // 父分类ID（支持层级分类）
	Level       int     // 层级深度
	Sort        int     // 排序
	CreatedBy   string
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// ConversationCategory 对话分类关联
type ConversationCategory struct {
	ConversationID string
	CategoryID     string
	CreatedAt      time.Time
}

// TagRepository 标签仓储接口
type TagRepository interface {
	Create(ctx context.Context, tag *Tag) error
	Update(ctx context.Context, tag *Tag) error
	Delete(ctx context.Context, tagID string) error
	GetByID(ctx context.Context, tagID string) (*Tag, error)
	ListByTenant(ctx context.Context, tenantID string, limit, offset int) ([]*Tag, int, error)
	GetByName(ctx context.Context, tenantID, name string) (*Tag, error)

	// 对话标签关联
	AddTagToConversation(ctx context.Context, conversationID, tagID string) error
	RemoveTagFromConversation(ctx context.Context, conversationID, tagID string) error
	GetConversationTags(ctx context.Context, conversationID string) ([]*Tag, error)
	GetConversationsByTag(ctx context.Context, tagID string, limit, offset int) ([]string, int, error)
}

// CategoryRepository 分类仓储接口
type CategoryRepository interface {
	Create(ctx context.Context, category *Category) error
	Update(ctx context.Context, category *Category) error
	Delete(ctx context.Context, categoryID string) error
	GetByID(ctx context.Context, categoryID string) (*Category, error)
	ListByTenant(ctx context.Context, tenantID string, parentID *string) ([]*Category, error)
	ListAll(ctx context.Context, tenantID string) ([]*Category, error)

	// 对话分类关联
	SetConversationCategory(ctx context.Context, conversationID, categoryID string) error
	RemoveConversationCategory(ctx context.Context, conversationID string) error
	GetConversationCategory(ctx context.Context, conversationID string) (*Category, error)
	GetConversationsByCategory(ctx context.Context, categoryID string, limit, offset int) ([]string, int, error)
}
