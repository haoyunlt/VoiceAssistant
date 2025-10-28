package biz

import (
	"context"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

// ClickHouseClient ClickHouse 客户端接口
type ClickHouseClient interface {
	Query(ctx context.Context, query string, args ...interface{}) (driver.Rows, error)
	QueryRow(ctx context.Context, query string, args ...interface{}) driver.Row
	Exec(ctx context.Context, query string, args ...interface{}) error
	Close() error
}

// CacheClient 缓存客户端接口
type CacheClient interface {
	Get(ctx context.Context, key string) (interface{}, error)
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error
	Delete(ctx context.Context, key string) error
}
