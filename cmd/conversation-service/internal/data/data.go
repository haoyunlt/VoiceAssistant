package data

import (
	"github.com/google/wire"
	"gorm.io/gorm"
)

// ProviderSet 数据层提供者集合
var ProviderSet = wire.NewSet(
	NewDB,
	NewConversationRepository,
	NewMessageRepository,
)

// Data 数据层结构
type Data struct {
	db *gorm.DB
}

// NewData 创建数据层
func NewData(db *gorm.DB) (*Data, error) {
	return &Data{
		db: db,
	}, nil
}
