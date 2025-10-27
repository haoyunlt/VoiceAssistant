package database

import (
	"context"
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

	// 连接池配置
	MaxIdleConns    int           // 最大空闲连接数，默认10
	MaxOpenConns    int           // 最大打开连接数，默认100
	ConnMaxLifetime time.Duration // 连接最大生命周期，默认1小时
	ConnMaxIdleTime time.Duration // 连接最大空闲时间，默认15分钟

	// 健康检查配置
	HealthCheckTimeout time.Duration // 健康检查超时，默认5秒
}

// NewDB 创建数据库连接（增强版）
func NewDB(c *Config, logger log.Logger) (*gorm.DB, error) {
	logHelper := log.NewHelper(logger)

	// 如果提供了Source，直接使用
	dsn := c.Source
	if dsn == "" {
		// 否则从Host/Port/User等构建DSN（不包含密码，后续单独添加）
		dsn = fmt.Sprintf(
			"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s TimeZone=Asia/Shanghai",
			c.Host, c.Port, c.User, c.Password, c.Database, c.SSLMode,
		)
	}

	// 安全日志：不记录密码
	logHelper.Infof("connecting to database: driver=%s host=%s:%d database=%s user=%s",
		c.Driver, c.Host, c.Port, c.Database, c.User)

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

	// 使用配置或默认值设置连接池
	maxIdleConns := c.MaxIdleConns
	if maxIdleConns == 0 {
		maxIdleConns = 10
	}
	maxOpenConns := c.MaxOpenConns
	if maxOpenConns == 0 {
		maxOpenConns = 100
	}
	connMaxLifetime := c.ConnMaxLifetime
	if connMaxLifetime == 0 {
		connMaxLifetime = time.Hour
	}
	connMaxIdleTime := c.ConnMaxIdleTime
	if connMaxIdleTime == 0 {
		connMaxIdleTime = 15 * time.Minute
	}

	sqlDB.SetMaxIdleConns(maxIdleConns)
	sqlDB.SetMaxOpenConns(maxOpenConns)
	sqlDB.SetConnMaxLifetime(connMaxLifetime)
	sqlDB.SetConnMaxIdleTime(connMaxIdleTime)

	logHelper.Infof("connection pool configured: maxIdle=%d maxOpen=%d maxLifetime=%v maxIdleTime=%v",
		maxIdleConns, maxOpenConns, connMaxLifetime, connMaxIdleTime)

	// 健康检查
	healthCheckTimeout := c.HealthCheckTimeout
	if healthCheckTimeout == 0 {
		healthCheckTimeout = 5 * time.Second
	}

	ctx, cancel := context.WithTimeout(context.Background(), healthCheckTimeout)
	defer cancel()

	if err := sqlDB.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("database health check failed: %w", err)
	}

	logHelper.Info("database connected and health check passed")
	return db, nil
}
