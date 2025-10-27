package resilience

import (
	"context"
	"errors"
	"sync"
	"time"
)

var (
	// ErrRateLimitExceeded 限流错误
	ErrRateLimitExceeded = errors.New("rate limit exceeded")
)

// TokenBucket 令牌桶限流器
type TokenBucket struct {
	mu           sync.Mutex
	capacity     int64         // 桶容量
	tokens       int64         // 当前令牌数
	refillRate   int64         // 每秒补充令牌数
	lastRefill   time.Time     // 上次补充时间
	refillPeriod time.Duration // 补充周期
}

// NewTokenBucket 创建令牌桶
func NewTokenBucket(capacity, refillRate int64) *TokenBucket {
	return &TokenBucket{
		capacity:     capacity,
		tokens:       capacity,
		refillRate:   refillRate,
		lastRefill:   time.Now(),
		refillPeriod: time.Second,
	}
}

// Allow 请求许可
func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	tb.refill()

	if tb.tokens > 0 {
		tb.tokens--
		return true
	}

	return false
}

// AllowN 请求N个令牌
func (tb *TokenBucket) AllowN(n int64) bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	tb.refill()

	if tb.tokens >= n {
		tb.tokens -= n
		return false
	}

	return false
}

// refill 补充令牌
func (tb *TokenBucket) refill() {
	now := time.Now()
	elapsed := now.Sub(tb.lastRefill)

	// 计算应该补充的令牌数
	tokensToAdd := int64(elapsed/tb.refillPeriod) * tb.refillRate

	if tokensToAdd > 0 {
		tb.tokens += tokensToAdd
		if tb.tokens > tb.capacity {
			tb.tokens = tb.capacity
		}
		tb.lastRefill = now
	}
}

// AvailableTokens 获取可用令牌数
func (tb *TokenBucket) AvailableTokens() int64 {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	tb.refill()
	return tb.tokens
}

// SlidingWindowLimiter 滑动窗口限流器
type SlidingWindowLimiter struct {
	mu       sync.Mutex
	window   time.Duration
	limit    int64
	requests []time.Time
}

// NewSlidingWindowLimiter 创建滑动窗口限流器
func NewSlidingWindowLimiter(window time.Duration, limit int64) *SlidingWindowLimiter {
	return &SlidingWindowLimiter{
		window:   window,
		limit:    limit,
		requests: make([]time.Time, 0),
	}
}

// Allow 请求许可
func (swl *SlidingWindowLimiter) Allow() bool {
	swl.mu.Lock()
	defer swl.mu.Unlock()

	now := time.Now()
	windowStart := now.Add(-swl.window)

	// 清理过期请求
	validRequests := make([]time.Time, 0)
	for _, req := range swl.requests {
		if req.After(windowStart) {
			validRequests = append(validRequests, req)
		}
	}
	swl.requests = validRequests

	// 检查是否超过限制
	if int64(len(swl.requests)) < swl.limit {
		swl.requests = append(swl.requests, now)
		return true
	}

	return false
}

// CurrentRate 获取当前速率
func (swl *SlidingWindowLimiter) CurrentRate() int64 {
	swl.mu.Lock()
	defer swl.mu.Unlock()

	now := time.Now()
	windowStart := now.Add(-swl.window)

	count := int64(0)
	for _, req := range swl.requests {
		if req.After(windowStart) {
			count++
		}
	}

	return count
}

// AdaptiveRateLimiter 自适应限流器
type AdaptiveRateLimiter struct {
	mu             sync.RWMutex
	baseLimit      int64
	currentLimit   int64
	minLimit       int64
	maxLimit       int64
	adjustInterval time.Duration
	lastAdjust     time.Time
	successCount   int64
	failureCount   int64
	tokenBucket    *TokenBucket
}

// NewAdaptiveRateLimiter 创建自适应限流器
func NewAdaptiveRateLimiter(baseLimit, minLimit, maxLimit int64, adjustInterval time.Duration) *AdaptiveRateLimiter {
	return &AdaptiveRateLimiter{
		baseLimit:      baseLimit,
		currentLimit:   baseLimit,
		minLimit:       minLimit,
		maxLimit:       maxLimit,
		adjustInterval: adjustInterval,
		lastAdjust:     time.Now(),
		tokenBucket:    NewTokenBucket(baseLimit, baseLimit),
	}
}

// Allow 请求许可
func (arl *AdaptiveRateLimiter) Allow() bool {
	arl.mu.Lock()
	defer arl.mu.Unlock()

	arl.maybeAdjust()

	return arl.tokenBucket.Allow()
}

// RecordSuccess 记录成功
func (arl *AdaptiveRateLimiter) RecordSuccess() {
	arl.mu.Lock()
	defer arl.mu.Unlock()
	arl.successCount++
}

// RecordFailure 记录失败
func (arl *AdaptiveRateLimiter) RecordFailure() {
	arl.mu.Lock()
	defer arl.mu.Unlock()
	arl.failureCount++
}

// maybeAdjust 可能调整限流
func (arl *AdaptiveRateLimiter) maybeAdjust() {
	now := time.Now()
	if now.Sub(arl.lastAdjust) < arl.adjustInterval {
		return
	}

	totalRequests := arl.successCount + arl.failureCount
	if totalRequests == 0 {
		return
	}

	errorRate := float64(arl.failureCount) / float64(totalRequests)

	// 根据错误率调整限流
	if errorRate > 0.1 { // 错误率超过10%，降低限流
		newLimit := int64(float64(arl.currentLimit) * 0.8)
		if newLimit < arl.minLimit {
			newLimit = arl.minLimit
		}
		arl.currentLimit = newLimit
		arl.tokenBucket = NewTokenBucket(newLimit, newLimit)
	} else if errorRate < 0.01 { // 错误率低于1%，提高限流
		newLimit := int64(float64(arl.currentLimit) * 1.2)
		if newLimit > arl.maxLimit {
			newLimit = arl.maxLimit
		}
		arl.currentLimit = newLimit
		arl.tokenBucket = NewTokenBucket(newLimit, newLimit)
	}

	// 重置计数器
	arl.successCount = 0
	arl.failureCount = 0
	arl.lastAdjust = now
}

// GetCurrentLimit 获取当前限流
func (arl *AdaptiveRateLimiter) GetCurrentLimit() int64 {
	arl.mu.RLock()
	defer arl.mu.RUnlock()
	return arl.currentLimit
}

// RateLimiterMiddleware 限流中间件
func RateLimiterMiddleware(limiter *TokenBucket) func(next func(ctx context.Context) error) func(ctx context.Context) error {
	return func(next func(ctx context.Context) error) func(ctx context.Context) error {
		return func(ctx context.Context) error {
			if !limiter.Allow() {
				return ErrRateLimitExceeded
			}
			return next(ctx)
		}
	}
}
