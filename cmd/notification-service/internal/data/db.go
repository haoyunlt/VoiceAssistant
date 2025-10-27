package data

import (
	"fmt"
	"time"
	"voiceassistant/cmd/notification-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
)

// Config is the database configuration
type Config struct {
	Driver string `json:"driver"`
	Source string `json:"source"`
}

// NewDB creates a new database connection
func NewDB(conf *Config, logger log.Logger) (*gorm.DB, error) {
	logHelper := log.NewHelper(logger)
	logHelper.Infof("connecting to database: driver=%s", conf.Driver)

	var dialector gorm.Dialector
	switch conf.Driver {
	case "postgres", "postgresql":
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

	// Configure connection pool
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}
	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)
	sqlDB.SetConnMaxLifetime(time.Hour)

	// Auto migrate tables
	if err := db.AutoMigrate(
		&domain.Notification{},
		&domain.Template{},
	); err != nil {
		logHelper.Errorf("failed to auto migrate: %v", err)
		return nil, err
	}

	logHelper.Info("database connected and migrated successfully")
	return db, nil
}
