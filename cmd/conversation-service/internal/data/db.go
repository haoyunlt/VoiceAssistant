package data

import (
	"fmt"
	"time"

	"gorm.io/gorm"
	"gorm.io/gorm/logger"
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
	// 连接池配置
	MaxIdleConns    int
	MaxOpenConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
}

// NewDB 创建数据库连接（使用统一数据库包）
func NewDB(config *DBConfig) (*gorm.DB, error) {
	// 设置默认连接池参数
	if config.MaxIdleConns == 0 {
		config.MaxIdleConns = 10
	}
	if config.MaxOpenConns == 0 {
		config.MaxOpenConns = 100
	}
	if config.ConnMaxLifetime == 0 {
		config.ConnMaxLifetime = time.Hour
	}
	if config.ConnMaxIdleTime == 0 {
		config.ConnMaxIdleTime = 10 * time.Minute
	}

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
	kLogger := log.NewStdLogger(nil)

	db, err := database.NewDB(dbConfig, kLogger)
	if err != nil {
		return nil, fmt.Errorf("failed to connect database: %w", err)
	}

	// 配置连接池
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get sql.DB: %w", err)
	}

	sqlDB.SetMaxIdleConns(config.MaxIdleConns)
	sqlDB.SetMaxOpenConns(config.MaxOpenConns)
	sqlDB.SetConnMaxLifetime(config.ConnMaxLifetime)
	sqlDB.SetConnMaxIdleTime(config.ConnMaxIdleTime)

	// 配置 GORM logger - 记录慢查询
	db.Logger = logger.Default.LogMode(logger.Warn)

	// 自动迁移
	if err := autoMigrate(db); err != nil {
		return nil, err
	}

	log.Log(log.LevelInfo,
		"msg", "database connected",
		"host", config.Host,
		"port", config.Port,
		"database", config.Database,
		"max_idle_conns", config.MaxIdleConns,
		"max_open_conns", config.MaxOpenConns,
	)

	return db, nil
}

// autoMigrate 自动迁移数据库表
func autoMigrate(db *gorm.DB) error {
	return db.AutoMigrate(
		&ConversationDO{},
		&MessageDO{},
	)
}
