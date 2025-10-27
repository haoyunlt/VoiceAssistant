package middleware

import (
	"context"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
)

// RateLimiterConfig 限流配置
type RateLimiterConfig struct {
	RedisClient *redis.Client
	MaxRequests int           // 最大请求数
	Window      time.Duration // 时间窗口
	KeyPrefix   string        // Redis key前缀
}

// RateLimiter 创建限流中间件
func RateLimiter(config RateLimiterConfig) gin.HandlerFunc {
	if config.KeyPrefix == "" {
		config.KeyPrefix = "rate_limit"
	}
	if config.MaxRequests == 0 {
		config.MaxRequests = 100
	}
	if config.Window == 0 {
		config.Window = time.Minute
	}

	return func(c *gin.Context) {
		// 1. 构建限流key（租户+用户维度）
		tenantID := c.GetString("tenant_id")
		userID := c.GetString("user_id")
		key := fmt.Sprintf("%s:%s:%s", config.KeyPrefix, tenantID, userID)

		ctx := context.Background()

		// 2. 增加计数
		pipe := config.RedisClient.Pipeline()
		incr := pipe.Incr(ctx, key)
		pipe.Expire(ctx, key, config.Window)
		_, err := pipe.Exec(ctx)

		if err != nil {
			c.JSON(500, gin.H{"error": "rate limiter error"})
			c.Abort()
			return
		}

		count := incr.Val()

		// 3. 检查是否超限
		if count > int64(config.MaxRequests) {
			c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", config.MaxRequests))
			c.Header("X-RateLimit-Remaining", "0")
			c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Add(config.Window).Unix()))

			c.JSON(429, gin.H{
				"error":       "rate limit exceeded",
				"retry_after": config.Window.Seconds(),
			})
			c.Abort()
			return
		}

		// 4. 设置响应头
		remaining := config.MaxRequests - int(count)
		c.Header("X-RateLimit-Limit", fmt.Sprintf("%d", config.MaxRequests))
		c.Header("X-RateLimit-Remaining", fmt.Sprintf("%d", remaining))
		c.Header("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Add(config.Window).Unix()))

		c.Next()
	}
}

// RateLimiterByIP IP级别限流
func RateLimiterByIP(config RateLimiterConfig) gin.HandlerFunc {
	if config.KeyPrefix == "" {
		config.KeyPrefix = "rate_limit_ip"
	}

	return func(c *gin.Context) {
		// 获取客户端IP
		clientIP := c.ClientIP()
		key := fmt.Sprintf("%s:%s", config.KeyPrefix, clientIP)

		ctx := context.Background()

		// 增加计数并设置过期
		pipe := config.RedisClient.Pipeline()
		incr := pipe.Incr(ctx, key)
		pipe.Expire(ctx, key, config.Window)
		_, err := pipe.Exec(ctx)

		if err != nil {
			c.JSON(500, gin.H{"error": "rate limiter error"})
			c.Abort()
			return
		}

		count := incr.Val()

		if count > int64(config.MaxRequests) {
			c.JSON(429, gin.H{
				"error":       "too many requests from this IP",
				"retry_after": config.Window.Seconds(),
			})
			c.Abort()
			return
		}

		c.Next()
	}
}
