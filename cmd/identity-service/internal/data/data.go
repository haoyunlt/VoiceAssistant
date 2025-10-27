package data

import (
	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

// Data is the data access layer struct.
type Data struct {
	db *gorm.DB
}

// NewData creates a new data access layer.
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
