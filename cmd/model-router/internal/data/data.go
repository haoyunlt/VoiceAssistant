package data

import (
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
)

// Data 数据访问层
type Data struct {
	db    *gorm.DB
	redis *redis.Client
}

// NewData 创建Data实例
func NewData(db *gorm.DB, redis *redis.Client, logger log.Logger) (*Data, func(), error) {
	cleanup := func() {
		helper := log.NewHelper(logger)
		helper.Info("closing the data resources")

		// 关闭数据库连接
		sqlDB, _ := db.DB()
		if sqlDB != nil {
			sqlDB.Close()
		}

		// 关闭Redis连接
		if redis != nil {
			redis.Close()
		}
	}
	return &Data{
		db:    db,
		redis: redis,
	}, cleanup, nil
}
