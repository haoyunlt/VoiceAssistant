package data

import (
	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
	"voiceassistant/pkg/database"
)

// Config 数据库配置
type Config struct {
	Driver string
	Source string
}

// NewDB 创建数据库连接（使用统一数据库包）
func NewDB(c *Config, logger log.Logger) (*gorm.DB, error) {
	// 使用统一数据库连接函数
	dbConfig := &database.Config{
		Driver: c.Driver,
		Source: c.Source,
	}

	return database.NewDB(dbConfig, logger)
}
