package data

import (
	"fmt"

	"gorm.io/gorm"
	"voiceassistant/pkg/database"
	"github.com/go-kratos/kratos/v2/log"
)

// DBConfig 数据库配置
type DBConfig struct {
	Host     string
	Port     int
	User     string
	Password string
	Database string
}

// NewDB 创建数据库连接（使用统一数据库包）
func NewDB(config *DBConfig) (*gorm.DB, error) {
	// 使用统一数据库连接函数
	dbConfig := &database.Config{
		Driver:   "postgres",
		Host:     config.Host,
		Port:     config.Port,
		User:     config.User,
		Password: config.Password,
		Database: config.Database,
		SSLMode:  "disable",
	}

	// 创建简单logger（conversation-service没有使用kratos）
	logger := log.NewStdLogger(nil)

	db, err := database.NewDB(dbConfig, logger)
	if err != nil {
		return nil, fmt.Errorf("failed to connect database: %w", err)
	}

	// 自动迁移
	if err := autoMigrate(db); err != nil {
		return nil, err
	}

	return db, nil
}

// autoMigrate 自动迁移数据库表
func autoMigrate(db *gorm.DB) error {
	return db.AutoMigrate(
		&ConversationDO{},
		&MessageDO{},
	)
}
