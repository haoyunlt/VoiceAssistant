package biz

import (
	"sync"
	"time"
	"voicehelper/cmd/ai-orchestrator/internal/domain"
)

// MemoryIntentCache 内存意图缓存实现
type MemoryIntentCache struct {
	mu      sync.RWMutex
	cache   map[string]*cacheEntry
	maxSize int
	stats   *CacheStats
}

// cacheEntry 缓存条目
type cacheEntry struct {
	intent    *domain.Intent
	expiresAt time.Time
}

// CacheStats 缓存统计
type CacheStats struct {
	mu        sync.RWMutex
	Hits      int64
	Misses    int64
	Evictions int64
	Size      int64
}

// NewMemoryIntentCache 创建内存缓存
func NewMemoryIntentCache(maxSize int) *MemoryIntentCache {
	c := &MemoryIntentCache{
		cache:   make(map[string]*cacheEntry),
		maxSize: maxSize,
		stats:   &CacheStats{},
	}

	// 启动清理协程
	go c.cleanupExpired()

	return c
}

// Get 获取缓存的意图
func (c *MemoryIntentCache) Get(key string) (*domain.Intent, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.cache[key]
	if !exists {
		c.stats.recordMiss()
		return nil, false
	}

	// 检查是否过期
	if time.Now().After(entry.expiresAt) {
		c.stats.recordMiss()
		return nil, false
	}

	c.stats.recordHit()
	return entry.intent, true
}

// Set 设置缓存
func (c *MemoryIntentCache) Set(key string, intent *domain.Intent, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()

	// 检查缓存大小
	if len(c.cache) >= c.maxSize {
		c.evictOldest()
	}

	// 如果TTL为0，使用默认10分钟
	if ttl == 0 {
		ttl = 10 * time.Minute
	}

	c.cache[key] = &cacheEntry{
		intent:    intent,
		expiresAt: time.Now().Add(ttl),
	}

	c.stats.recordSet()
}

// Delete 删除缓存
func (c *MemoryIntentCache) Delete(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	delete(c.cache, key)
	c.stats.recordDelete()
}

// Clear 清空缓存
func (c *MemoryIntentCache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.cache = make(map[string]*cacheEntry)
	c.stats.reset()
}

// evictOldest 驱逐最旧的条目
func (c *MemoryIntentCache) evictOldest() {
	var oldestKey string
	var oldestTime time.Time
	first := true

	for key, entry := range c.cache {
		if first || entry.expiresAt.Before(oldestTime) {
			oldestKey = key
			oldestTime = entry.expiresAt
			first = false
		}
	}

	if oldestKey != "" {
		delete(c.cache, oldestKey)
		c.stats.recordEviction()
	}
}

// cleanupExpired 清理过期条目
func (c *MemoryIntentCache) cleanupExpired() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		c.mu.Lock()
		now := time.Now()

		for key, entry := range c.cache {
			if now.After(entry.expiresAt) {
				delete(c.cache, key)
				c.stats.recordEviction()
			}
		}

		c.mu.Unlock()
	}
}

// GetStats 获取缓存统计
func (c *MemoryIntentCache) GetStats() CacheStats {
	c.stats.mu.RLock()
	defer c.stats.mu.RUnlock()

	c.mu.RLock()
	size := int64(len(c.cache))
	c.mu.RUnlock()

	return CacheStats{
		Hits:      c.stats.Hits,
		Misses:    c.stats.Misses,
		Evictions: c.stats.Evictions,
		Size:      size,
	}
}

// HitRate 缓存命中率
func (c *MemoryIntentCache) HitRate() float64 {
	stats := c.GetStats()
	total := stats.Hits + stats.Misses
	if total == 0 {
		return 0
	}
	return float64(stats.Hits) / float64(total)
}

// CacheStats 方法

func (s *CacheStats) recordHit() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Hits++
}

func (s *CacheStats) recordMiss() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Misses++
}

func (s *CacheStats) recordSet() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Size++
}

func (s *CacheStats) recordDelete() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.Size > 0 {
		s.Size--
	}
}

func (s *CacheStats) recordEviction() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Evictions++
	if s.Size > 0 {
		s.Size--
	}
}

func (s *CacheStats) reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Hits = 0
	s.Misses = 0
	s.Evictions = 0
	s.Size = 0
}

// RedisIntentCache Redis意图缓存实现（占位）
type RedisIntentCache struct {
	// TODO: 实现Redis缓存
	// redisClient *redis.Client
	// keyPrefix   string
}

// NewRedisIntentCache 创建Redis缓存
func NewRedisIntentCache() *RedisIntentCache {
	return &RedisIntentCache{}
}

// Get 获取缓存的意图
func (c *RedisIntentCache) Get(key string) (*domain.Intent, bool) {
	// TODO: 实现Redis GET
	return nil, false
}

// Set 设置缓存
func (c *RedisIntentCache) Set(key string, intent *domain.Intent, ttl time.Duration) {
	// TODO: 实现Redis SET with TTL
}

// Delete 删除缓存
func (c *RedisIntentCache) Delete(key string) {
	// TODO: 实现Redis DELETE
}

// Clear 清空缓存
func (c *RedisIntentCache) Clear() {
	// TODO: 实现Redis清空（按前缀删除）
}
