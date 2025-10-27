package database

import (
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormLogger "gorm.io/gorm/logger"
)

// Config 数据库配置
type Config struct {
	Driver   string
	Source   string
	Host     string
	Port     int
	User     string
	Password string
	Database string
	SSLMode  string
}

// NewDB 创建数据库连接（统一版本）
func NewDB(c *Config, logger log.Logger) (*gorm.DB, error) {
	logHelper := log.NewHelper(logger)

	// 如果提供了Source，直接使用
	dsn := c.Source
	if dsn == "" {
		// 否则从Host/Port/User等构建DSN
		dsn = fmt.Sprintf(
			"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s TimeZone=Asia/Shanghai",
			c.Host, c.Port, c.User, c.Password, c.Database, c.SSLMode,
		)
	}

	logHelper.Infof("connecting to database: %s", c.Driver)

	var dialector gorm.Dialector
	switch c.Driver {
	case "postgres", "":
		dialector = postgres.Open(dsn)
	default:
		return nil, fmt.Errorf("unsupported database driver: %s", c.Driver)
	}

	db, err := gorm.Open(dialector, &gorm.Config{
		Logger: gormLogger.Default.LogMode(gormLogger.Info),
		NowFunc: func() time.Time {
			return time.Now().UTC()
		},
	})
	if err != nil {
		logHelper.Errorf("failed to connect database: %v", err)
		return nil, fmt.Errorf("failed to connect database: %w", err)
	}

	// 配置连接池
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get sql.DB: %w", err)
	}

	// 设置连接池参数
	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)
	sqlDB.SetConnMaxLifetime(time.Hour)

	logHelper.Info("database connected successfully")
	return db, nil
}
