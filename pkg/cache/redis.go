package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisCache is a Redis-based cache implementation.
type RedisCache struct {
	client  *redis.Client
	options *CacheOptions
}

// NewRedisCache creates a new Redis cache.
func NewRedisCache(addr string, password string, db int, opts *CacheOptions) *RedisCache {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	if opts == nil {
		opts = &CacheOptions{
			DefaultTTL: 5 * time.Minute,
			Serializer: &JSONSerializer{},
		}
	}

	return &RedisCache{
		client:  client,
		options: opts,
	}
}

// makeKey 生成带前缀的键
func (c *RedisCache) makeKey(key string) string {
	if c.options.KeyPrefix != "" {
		return fmt.Sprintf("%s:%s", c.options.KeyPrefix, key)
	}
	return key
}

// Get gets a value from cache.
func (c *RedisCache) Get(ctx context.Context, key string) (string, error) {
	return c.client.Get(ctx, c.makeKey(key)).Result()
}

// Set sets a value in cache with TTL.
func (c *RedisCache) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	if ttl == 0 {
		ttl = c.options.DefaultTTL
	}
	return c.client.Set(ctx, c.makeKey(key), value, ttl).Err()
}

// GetBytes 获取字节数组
func (c *RedisCache) GetBytes(ctx context.Context, key string) ([]byte, error) {
	return c.client.Get(ctx, c.makeKey(key)).Bytes()
}

// SetBytes 设置字节数组
func (c *RedisCache) SetBytes(ctx context.Context, key string, value []byte, ttl time.Duration) error {
	if ttl == 0 {
		ttl = c.options.DefaultTTL
	}
	return c.client.Set(ctx, c.makeKey(key), value, ttl).Err()
}

// Delete deletes a key from cache.
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, c.makeKey(key)).Err()
}

// Exists checks if a key exists in cache.
func (c *RedisCache) Exists(ctx context.Context, key string) (bool, error) {
	result, err := c.client.Exists(ctx, c.makeKey(key)).Result()
	return result > 0, err
}

// Incr 自增
func (c *RedisCache) Incr(ctx context.Context, key string) (int64, error) {
	return c.client.Incr(ctx, c.makeKey(key)).Result()
}

// Decr 自减
func (c *RedisCache) Decr(ctx context.Context, key string) (int64, error) {
	return c.client.Decr(ctx, c.makeKey(key)).Result()
}

// Expire 设置过期时间
func (c *RedisCache) Expire(ctx context.Context, key string, ttl time.Duration) error {
	return c.client.Expire(ctx, c.makeKey(key), ttl).Err()
}

// TTL 获取剩余过期时间
func (c *RedisCache) TTL(ctx context.Context, key string) (time.Duration, error) {
	return c.client.TTL(ctx, c.makeKey(key)).Result()
}

// GetObject 获取对象（自动反序列化）
func (c *RedisCache) GetObject(ctx context.Context, key string, dest interface{}) error {
	data, err := c.GetBytes(ctx, key)
	if err != nil {
		return err
	}

	return c.options.Serializer.Deserialize(data, dest)
}

// SetObject 设置对象（自动序列化）
func (c *RedisCache) SetObject(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	data, err := c.options.Serializer.Serialize(value)
	if err != nil {
		return err
	}

	return c.SetBytes(ctx, key, data, ttl)
}

// Close closes the Redis client.
func (c *RedisCache) Close() error {
	return c.client.Close()
}

// JSONSerializer JSON序列化器
type JSONSerializer struct{}

// Serialize 序列化
func (s *JSONSerializer) Serialize(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}

// Deserialize 反序列化
func (s *JSONSerializer) Deserialize(data []byte, v interface{}) error {
	return json.Unmarshal(data, v)
}
