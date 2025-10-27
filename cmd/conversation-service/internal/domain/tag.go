package domain

import "time"

// Tag 对话标签
type Tag struct {
	ID          string
	Name        string
	Description string
	Color       string
	Category    string
	Count       int
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// TagRepository 标签仓储接口
type TagRepository interface {
	CreateTag(tag *Tag) error
	GetTag(id string) (*Tag, error)
	GetTagByName(name string) (*Tag, error)
	GetOrCreateTag(name string) (*Tag, error)
	ListTags(limit, offset int) ([]*Tag, error)
	GetPopularTagsByCategory(category string, limit int) ([]*Tag, error)
	UpdateTag(tag *Tag) error
	DeleteTag(id string) error
	IncrementCount(id string) error
}
