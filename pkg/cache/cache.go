package cache

import (
	"context"
	"time"
)

// Cache 缓存接口
type Cache interface {
	// Get 获取缓存值
	Get(ctx context.Context, key string) (string, error)

	// Set 设置缓存值
	Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error

	// Delete 删除缓存
	Delete(ctx context.Context, key string) error

	// Exists 检查键是否存在
	Exists(ctx context.Context, key string) (bool, error)

	// GetBytes 获取字节数组
	GetBytes(ctx context.Context, key string) ([]byte, error)

	// SetBytes 设置字节数组
	SetBytes(ctx context.Context, key string, value []byte, ttl time.Duration) error

	// Incr 自增
	Incr(ctx context.Context, key string) (int64, error)

	// Decr 自减
	Decr(ctx context.Context, key string) (int64, error)

	// Expire 设置过期时间
	Expire(ctx context.Context, key string, ttl time.Duration) error

	// TTL 获取剩余过期时间
	TTL(ctx context.Context, key string) (time.Duration, error)

	// Close 关闭连接
	Close() error
}

// CacheOptions 缓存选项
type CacheOptions struct {
	// 默认过期时间
	DefaultTTL time.Duration

	// 键前缀
	KeyPrefix string

	// 是否启用压缩
	EnableCompression bool

	// 序列化方式
	Serializer Serializer
}

// Serializer 序列化器接口
type Serializer interface {
	Serialize(v interface{}) ([]byte, error)
	Deserialize(data []byte, v interface{}) error
}
