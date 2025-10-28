package data

import (
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
)

// Config 数据库配置
type Config struct {
	Driver          string
	Source          string
	MaxIdleConns    int
	MaxOpenConns    int
	ConnMaxLifetime time.Duration
}

// NewDB 创建数据库连接
func NewDB(c *Config, logger log.Logger) (*gorm.DB, error) {
	helper := log.NewHelper(logger)

	// 根据驱动选择适配器
	var dialector gorm.Dialector
	switch c.Driver {
	case "postgres", "postgresql":
		dialector = postgres.Open(c.Source)
	default:
		return nil, fmt.Errorf("unsupported database driver: %s", c.Driver)
	}

	// 配置GORM日志
	gormLogger := gormlogger.New(
		&logAdapter{helper: helper},
		gormlogger.Config{
			SlowThreshold:             200 * time.Millisecond,
			LogLevel:                  gormlogger.Info,
			IgnoreRecordNotFoundError: true,
			Colorful:                  false,
		},
	)

	// 创建连接
	db, err := gorm.Open(dialector, &gorm.Config{
		Logger:                 gormLogger,
		SkipDefaultTransaction: true, // 提升性能
		PrepareStmt:            true, // 预编译SQL
	})
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// 获取底层sql.DB
	sqlDB, err := db.DB()
	if err != nil {
		return nil, fmt.Errorf("failed to get sql.DB: %w", err)
	}

	// 设置连接池参数
	if c.MaxIdleConns > 0 {
		sqlDB.SetMaxIdleConns(c.MaxIdleConns)
	} else {
		sqlDB.SetMaxIdleConns(10) // 默认值
	}

	if c.MaxOpenConns > 0 {
		sqlDB.SetMaxOpenConns(c.MaxOpenConns)
	} else {
		sqlDB.SetMaxOpenConns(100) // 默认值
	}

	if c.ConnMaxLifetime > 0 {
		sqlDB.SetConnMaxLifetime(c.ConnMaxLifetime)
	} else {
		sqlDB.SetConnMaxLifetime(time.Hour) // 默认1小时
	}

	helper.Info("database connected successfully")
	return db, nil
}

// logAdapter GORM日志适配器
type logAdapter struct {
	helper *log.Helper
}

func (l *logAdapter) Printf(format string, args ...interface{}) {
	l.helper.Infof(format, args...)
}
