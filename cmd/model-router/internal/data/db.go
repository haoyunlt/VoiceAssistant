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
	Driver string
	Source string
}

// NewDB 创建数据库连接
func NewDB(conf *Config, logger log.Logger) (*gorm.DB, error) {
	logHelper := log.NewHelper(logger)
	logHelper.Infof("connecting to database: %s", conf.Driver)

	var dialector gorm.Dialector
	switch conf.Driver {
	case "postgres":
		dialector = postgres.Open(conf.Source)
	default:
		return nil, fmt.Errorf("unsupported database driver: %s", conf.Driver)
	}

	db, err := gorm.Open(dialector, &gorm.Config{
		Logger: gormlogger.Default.LogMode(gormlogger.Info),
		NowFunc: func() time.Time {
			return time.Now().UTC()
		},
	})
	if err != nil {
		logHelper.Errorf("failed to connect database: %v", err)
		return nil, err
	}

	// 配置连接池
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}
	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)
	sqlDB.SetConnMaxLifetime(time.Hour)

	logHelper.Info("database connected successfully")
	return db, nil
}
