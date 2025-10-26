package cache

import (
	"context"
	"time"

	"github.com/go-redis/redis/v8"
)

// RedisCache is a Redis-based cache implementation.
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache creates a new Redis cache.
func NewRedisCache(addr string, password string, db int) *RedisCache {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	return &RedisCache{
		client: client,
	}
}

// Get gets a value from cache.
func (c *RedisCache) Get(ctx context.Context, key string) (string, error) {
	return c.client.Get(ctx, key).Result()
}

// Set sets a value in cache with TTL.
func (c *RedisCache) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	return c.client.Set(ctx, key, value, ttl).Err()
}

// Delete deletes a key from cache.
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, key).Err()
}

// Exists checks if a key exists in cache.
func (c *RedisCache) Exists(ctx context.Context, key string) (bool, error) {
	result, err := c.client.Exists(ctx, key).Result()
	return result > 0, err
}

// Close closes the Redis client.
func (c *RedisCache) Close() error {
	return c.client.Close()
}
