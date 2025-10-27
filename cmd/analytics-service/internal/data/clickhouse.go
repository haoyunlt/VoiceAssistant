package data

import (
	"context"
	"fmt"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

// ClickHouseConfig ClickHouse 配置
type ClickHouseConfig struct {
	Addr     string
	Database string
	Username string
	Password string
}

// ClickHouseClient ClickHouse 客户端
type ClickHouseClient struct {
	conn driver.Conn
}

// NewClickHouseClient 创建 ClickHouse 客户端
func NewClickHouseClient(config *ClickHouseConfig) (*ClickHouseClient, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{config.Addr},
		Auth: clickhouse.Auth{
			Database: config.Database,
			Username: config.Username,
			Password: config.Password,
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to ClickHouse: %w", err)
	}

	// 测试连接
	if err := conn.Ping(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to ping ClickHouse: %w", err)
	}

	return &ClickHouseClient{
		conn: conn,
	}, nil
}

// Query 执行查询
func (c *ClickHouseClient) Query(ctx context.Context, query string, args ...interface{}) (driver.Rows, error) {
	return c.conn.Query(ctx, query, args...)
}

// QueryRow 查询单行
func (c *ClickHouseClient) QueryRow(ctx context.Context, query string, args ...interface{}) driver.Row {
	return c.conn.QueryRow(ctx, query, args...)
}

// Exec 执行语句
func (c *ClickHouseClient) Exec(ctx context.Context, query string, args ...interface{}) error {
	return c.conn.Exec(ctx, query, args...)
}

// Close 关闭连接
func (c *ClickHouseClient) Close() error {
	return c.conn.Close()
}
