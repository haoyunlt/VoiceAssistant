package middleware

import (
	"context"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
)

// RateLimiter Redis 分布式限流器
type RateLimiter struct {
	redis  *redis.Client
	limits map[string]RateLimit
	window time.Duration
	logger *log.Helper
}

// RateLimit 限流配置
type RateLimit struct {
	RequestsPerMinute int           // 每分钟请求数
	Burst             int           // 突发容量
	Window            time.Duration // 时间窗口
}

// RateLimiterConfig 限流器配置
type RateLimiterConfig struct {
	Enabled     bool
	DefaultRPM  int
	PremiumRPM  int
	Burst       int
	FallbackMode string // "allow" 或 "deny"
}

// NewRateLimiter 创建限流器
func NewRateLimiter(redis *redis.Client, config *RateLimiterConfig, logger log.Logger) *RateLimiter {
	if config == nil {
		config = &RateLimiterConfig{
			Enabled:      true,
			DefaultRPM:   200,
			PremiumRPM:   1000,
			Burst:        100,
			FallbackMode: "allow",
		}
	}

	return &RateLimiter{
		redis: redis,
		limits: map[string]RateLimit{
			"default": {
				RequestsPerMinute: config.DefaultRPM,
				Burst:             config.Burst,
				Window:            time.Minute,
			},
			"premium": {
				RequestsPerMinute: config.PremiumRPM,
				Burst:             config.Burst * 5,
				Window:            time.Minute,
			},
		},
		window: time.Minute,
		logger: log.NewHelper(log.With(logger, "module", "ratelimit")),
	}
}

// Middleware 限流中间件
func (rl *RateLimiter) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 跳过健康检查
		if c.Request.URL.Path == "/health" || c.Request.URL.Path == "/metrics" {
			c.Next()
			return
		}

		// 获取租户和用户信息
		tenantID := c.GetString("tenant_id")
		userID := c.GetString("user_id")

		// 如果未认证，使用 IP 作为限流维度
		if userID == "" {
			userID = c.ClientIP()
		}
		if tenantID == "" {
			tenantID = "anonymous"
		}

		// 确定限流级别（可以从用户信息中获取）
		tier := rl.getTier(c)

		// 构建限流键（租户+用户维度）
		key := fmt.Sprintf("ratelimit:%s:%s:%s", tier, tenantID, userID)

		// 检查限流
		allowed, remaining, resetAt, err := rl.checkLimit(c.Request.Context(), key, tier)
		if err != nil {
			// 限流器故障，根据配置决定放行或拒绝
			rl.logger.Errorf("Rate limiter error: %v", err)
			// 这里选择降级放行（可配置）
			c.Next()
			return
		}

		// 设置响应头
		limit := rl.limits[tier]
		c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", limit.RequestsPerMinute))
		c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", remaining))
		c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", resetAt))

		if !allowed {
			rl.logger.Warnf("Rate limit exceeded: tenant=%s, user=%s, tier=%s", tenantID, userID, tier)
			c.JSON(429, gin.H{
				"code":        429,
				"message":     "Too many requests",
				"retry_after": resetAt - time.Now().Unix(),
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// checkLimit 检查限流（使用 Lua 脚本实现令牌桶算法）
func (rl *RateLimiter) checkLimit(ctx context.Context, key string, tier string) (allowed bool, remaining int, resetAt int64, err error) {
	limit := rl.limits[tier]

	// 使用 Lua 脚本实现原子操作
	script := redis.NewScript(`
		local key = KEYS[1]
		local limit = tonumber(ARGV[1])
		local window = tonumber(ARGV[2])
		local current_time = tonumber(ARGV[3])

		-- 获取当前计数
		local current = redis.call('GET', key)

		if current and tonumber(current) >= limit then
			local ttl = redis.call('TTL', key)
			return {0, 0, current_time + ttl}
		end

		-- 增加计数
		local new_count = redis.call('INCR', key)

		-- 如果是第一次请求，设置过期时间
		if new_count == 1 then
			redis.call('EXPIRE', key, window)
		end

		-- 计算剩余额度
		local remaining = limit - new_count
		local ttl = redis.call('TTL', key)
		local reset_at = current_time + ttl

		return {1, remaining, reset_at}
	`)

	result, err := script.Run(
		ctx,
		rl.redis,
		[]string{key},
		limit.RequestsPerMinute,
		int(limit.Window.Seconds()),
		time.Now().Unix(),
	).Result()

	if err != nil {
		return false, 0, 0, fmt.Errorf("failed to execute rate limit script: %w", err)
	}

	// 解析结果
	values := result.([]interface{})
	allowed = values[0].(int64) == 1
	remaining = int(values[1].(int64))
	resetAt = values[2].(int64)

	return allowed, remaining, resetAt, nil
}

// getTier 获取用户限流级别
func (rl *RateLimiter) getTier(c *gin.Context) string {
	// 可以从用户信息中获取（例如从 JWT claims）
	// 这里简化处理，默认使用 default
	tier := c.GetString("tier")
	if tier == "" {
		tier = "default"
	}

	// 检查是否存在该级别
	if _, ok := rl.limits[tier]; !ok {
		tier = "default"
	}

	return tier
}

// GetStats 获取限流统计（用于监控）
func (rl *RateLimiter) GetStats(ctx context.Context, tenantID, userID string) (map[string]interface{}, error) {
	stats := make(map[string]interface{})

	for tier := range rl.limits {
		key := fmt.Sprintf("ratelimit:%s:%s:%s", tier, tenantID, userID)
		count, err := rl.redis.Get(ctx, key).Int()
		if err != nil && err != redis.Nil {
			return nil, err
		}

		ttl, err := rl.redis.TTL(ctx, key).Result()
		if err != nil {
			return nil, err
		}

		stats[tier] = map[string]interface{}{
			"current":   count,
			"limit":     rl.limits[tier].RequestsPerMinute,
			"remaining": rl.limits[tier].RequestsPerMinute - count,
			"reset_in":  int(ttl.Seconds()),
		}
	}

	return stats, nil
}
