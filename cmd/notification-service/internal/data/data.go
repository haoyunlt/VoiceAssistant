package data

import (
	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

type Data struct {
	db *gorm.DB
}

func NewData(db *gorm.DB, logger log.Logger) (*Data, func(), error) {
	cleanup := func() {
		log.NewHelper(logger).Info("closing the data resources")
		sqlDB, _ := db.DB()
		if sqlDB != nil {
			sqlDB.Close()
		}
	}
	return &Data{db: db}, cleanup, nil
}
