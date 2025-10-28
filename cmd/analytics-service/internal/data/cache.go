package data

import (
	"context"
	"encoding/json"
	"sync"
	"time"
)

// CacheItem 缓存项
type cacheItem struct {
	value      interface{}
	expiration time.Time
}

// MemoryCache 内存缓存实现
type MemoryCache struct {
	items sync.Map
	mutex sync.RWMutex
}

// NewMemoryCache 创建内存缓存
func NewMemoryCache() *MemoryCache {
	cache := &MemoryCache{}

	// 启动清理 goroutine
	go cache.cleanupExpired()

	return cache
}

// Get 获取缓存值
func (c *MemoryCache) Get(ctx context.Context, key string) (interface{}, error) {
	value, ok := c.items.Load(key)
	if !ok {
		return nil, ErrCacheKeyNotFound
	}

	item := value.(*cacheItem)

	// 检查是否过期
	if time.Now().After(item.expiration) {
		c.items.Delete(key)
		return nil, ErrCacheKeyNotFound
	}

	return item.value, nil
}

// Set 设置缓存值
func (c *MemoryCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	// 序列化值（确保可以被缓存）
	_, err := json.Marshal(value)
	if err != nil {
		return err
	}

	item := &cacheItem{
		value:      value,
		expiration: time.Now().Add(expiration),
	}

	c.items.Store(key, item)
	return nil
}

// Delete 删除缓存值
func (c *MemoryCache) Delete(ctx context.Context, key string) error {
	c.items.Delete(key)
	return nil
}

// cleanupExpired 清理过期项
func (c *MemoryCache) cleanupExpired() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		now := time.Now()
		c.items.Range(func(key, value interface{}) bool {
			item := value.(*cacheItem)
			if now.After(item.expiration) {
				c.items.Delete(key)
			}
			return true
		})
	}
}

// ErrCacheKeyNotFound 缓存键不存在错误
var ErrCacheKeyNotFound = &CacheError{Message: "cache key not found"}

// CacheError 缓存错误
type CacheError struct {
	Message string
}

func (e *CacheError) Error() string {
	return e.Message
}
