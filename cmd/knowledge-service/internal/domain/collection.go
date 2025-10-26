package domain

import "time"

// Collection 集合领域模型
type Collection struct {
	ID            string
	UserID        string
	TenantID      string
	Name          string
	Description   string
	Type          CollectionType
	Metadata      CollectionMetadata
	CreatedAt     time.Time
	UpdatedAt     time.Time
	DocumentCount int
}

// CollectionType 集合类型
type CollectionType int

const (
	CollectionTypeUnspecified CollectionType = iota
	CollectionTypePersonal                   // 个人
	CollectionTypeShared                     // 共享
	CollectionTypePublic                     // 公开
)

// CollectionMetadata 集合元数据
type CollectionMetadata struct {
	Tags         map[string]string
	AllowedUsers []string
}

// CollectionRepository 集合仓储接口
type CollectionRepository interface {
	Create(collection *Collection) error
	GetByID(id string) (*Collection, error)
	Update(collection *Collection) error
	Delete(id string) error
	List(userID, tenantID string, collectionType *CollectionType, page, pageSize int) ([]*Collection, int, error)
	IncrementDocumentCount(id string, delta int) error
}
