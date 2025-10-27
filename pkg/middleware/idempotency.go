package middleware

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
)

const (
	IdempotencyKeyHeader = "Idempotency-Key"
	IdempotencyTTL       = 120 * time.Second // 幂等性保持时间
)

// IdempotencyConfig 幂等性配置
type IdempotencyConfig struct {
	RedisClient *redis.Client
	KeyPrefix   string
	TTL         time.Duration
}

// Idempotency 创建幂等性中间件
func Idempotency(config IdempotencyConfig) gin.HandlerFunc {
	if config.KeyPrefix == "" {
		config.KeyPrefix = "idempotency"
	}
	if config.TTL == 0 {
		config.TTL = IdempotencyTTL
	}

	return func(c *gin.Context) {
		// 1. 获取幂等性Key
		idempotencyKey := c.GetHeader(IdempotencyKeyHeader)
		if idempotencyKey == "" {
			// 没有提供幂等性Key，直接放行
			c.Next()
			return
		}

		// 2. 构建Redis Key
		tenantID := c.GetString("tenant_id")
		userID := c.GetString("user_id")

		// 使用请求方法、路径、幂等性Key和用户信息生成唯一key
		hashInput := fmt.Sprintf("%s:%s:%s:%s:%s",
			c.Request.Method,
			c.Request.URL.Path,
			idempotencyKey,
			tenantID,
			userID,
		)
		hash := sha256.Sum256([]byte(hashInput))
		redisKey := fmt.Sprintf("%s:%s", config.KeyPrefix, hex.EncodeToString(hash[:]))

		ctx := context.Background()

		// 3. 检查是否已处理
		result, err := config.RedisClient.Get(ctx, redisKey).Result()
		if err == nil {
			// 已处理，返回缓存结果
			c.Header("X-Idempotency-Replayed", "true")
			c.Data(200, "application/json", []byte(result))
			c.Abort()
			return
		}

		// 4. 尝试设置处理锁
		lockKey := fmt.Sprintf("%s:lock", redisKey)
		locked, err := config.RedisClient.SetNX(ctx, lockKey, "1", 30*time.Second).Result()
		if err != nil {
			c.JSON(500, gin.H{"error": "idempotency check failed"})
			c.Abort()
			return
		}

		if !locked {
			// 正在处理中
			c.JSON(409, gin.H{"error": "request is being processed"})
			c.Abort()
			return
		}

		// 5. 捕获响应
		writer := &responseWriter{
			ResponseWriter: c.Writer,
			body:           []byte{},
		}
		c.Writer = writer

		c.Next()

		// 6. 如果请求成功，缓存结果
		if c.Writer.Status() >= 200 && c.Writer.Status() < 300 {
			config.RedisClient.Set(ctx, redisKey, writer.body, config.TTL)
		}

		// 7. 释放锁
		config.RedisClient.Del(ctx, lockKey)
	}
}

// responseWriter 用于捕获响应body
type responseWriter struct {
	gin.ResponseWriter
	body []byte
}

func (w *responseWriter) Write(data []byte) (int, error) {
	w.body = append(w.body, data...)
	return w.ResponseWriter.Write(data)
}

func (w *responseWriter) WriteString(s string) (int, error) {
	w.body = append(w.body, []byte(s)...)
	return w.ResponseWriter.WriteString(s)
}
