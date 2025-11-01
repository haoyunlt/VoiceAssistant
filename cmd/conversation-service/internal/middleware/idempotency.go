package middleware

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
)

// IdempotencyManager 幂等性管理器
type IdempotencyManager struct {
	redis  *redis.Client
	ttl    time.Duration
	logger *log.Helper
}

// IdempotencyConfig 幂等性配置
type IdempotencyConfig struct {
	Enabled bool
	TTL     time.Duration
	// 需要幂等性保护的路径前缀
	ProtectedPaths []string
}

// NewIdempotencyManager 创建幂等性管理器
func NewIdempotencyManager(redis *redis.Client, config *IdempotencyConfig, logger log.Logger) *IdempotencyManager {
	if config == nil {
		config = &IdempotencyConfig{
			Enabled: true,
			TTL:     120 * time.Second,
			ProtectedPaths: []string{
				"/api/v1/conversations",
				"/api/v1/messages",
			},
		}
	}

	return &IdempotencyManager{
		redis:  redis,
		ttl:    config.TTL,
		logger: log.NewHelper(log.With(logger, "module", "idempotency")),
	}
}

// Middleware 幂等性中间件
func (im *IdempotencyManager) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 仅对写操作启用幂等性
		if c.Request.Method == "GET" || c.Request.Method == "HEAD" || c.Request.Method == "OPTIONS" {
			c.Next()
			return
		}

		// 获取或生成幂等键
		idempotencyKey, err := im.getIdempotencyKey(c)
		if err != nil {
			im.logger.Errorf("Failed to get idempotency key: %v", err)
			c.JSON(500, gin.H{
				"code":    500,
				"message": "Internal server error",
			})
			c.Abort()
			return
		}

		// 构建 Redis 键
		userID := c.GetString("user_id")
		if userID == "" {
			userID = c.ClientIP()
		}
		key := fmt.Sprintf("idempotency:%s:%s", userID, idempotencyKey)

		// 检查是否已处理
		cached, err := im.redis.Get(c.Request.Context(), key).Bytes()
		if err == nil && len(cached) > 0 {
			// 已处理，返回缓存结果
			im.logger.Infof("Returning cached response for key: %s", idempotencyKey)
			c.Data(200, "application/json", cached)
			c.Abort()
			return
		}

		// 设置临时锁（防止并发重复请求）
		lockKey := key + ":lock"
		locked, err := im.redis.SetNX(c.Request.Context(), lockKey, "1", 10*time.Second).Result()
		if err != nil {
			im.logger.Errorf("Failed to acquire lock: %v", err)
			// 降级：允许请求通过
			c.Next()
			return
		}

		if !locked {
			// 其他请求正在处理
			im.logger.Warnf("Concurrent request detected for key: %s", idempotencyKey)
			c.JSON(409, gin.H{
				"code":    409,
				"message": "Request is being processed, please wait",
			})
			c.Abort()
			return
		}

		// 确保清理锁
		defer func() {
			im.redis.Del(c.Request.Context(), lockKey)
		}()

		// 捕获响应
		writer := &responseWriter{
			ResponseWriter: c.Writer,
			body:           &bytes.Buffer{},
		}
		c.Writer = writer

		c.Next()

		// 缓存响应（仅成功请求）
		statusCode := writer.Status()
		if statusCode >= 200 && statusCode < 300 {
			responseBody := writer.body.Bytes()
			if len(responseBody) > 0 {
				err := im.redis.Set(c.Request.Context(), key, responseBody, im.ttl).Err()
				if err != nil {
					im.logger.Errorf("Failed to cache response: %v", err)
				} else {
					im.logger.Debugf("Cached response for key: %s", idempotencyKey)
				}
			}
		}
	}
}

// getIdempotencyKey 获取或生成幂等键
func (im *IdempotencyManager) getIdempotencyKey(c *gin.Context) (string, error) {
	// 1. 优先使用客户端提供的幂等键
	idempotencyKey := c.GetHeader("X-Idempotency-Key")
	if idempotencyKey != "" {
		return idempotencyKey, nil
	}

	// 2. 基于请求内容生成幂等键
	bodyBytes, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read request body: %w", err)
	}

	// 恢复请求体（供后续处理）
	c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))

	// 生成 SHA256 哈希
	hash := sha256.New()
	hash.Write([]byte(c.Request.Method))
	hash.Write([]byte(c.Request.URL.Path))
	hash.Write(bodyBytes)

	idempotencyKey = hex.EncodeToString(hash.Sum(nil))

	return idempotencyKey, nil
}

// responseWriter 响应写入器（用于捕获响应）
type responseWriter struct {
	gin.ResponseWriter
	body *bytes.Buffer
}

func (w *responseWriter) Write(b []byte) (int, error) {
	// 同时写入缓冲区和原始 writer
	w.body.Write(b)
	return w.ResponseWriter.Write(b)
}

func (w *responseWriter) WriteString(s string) (int, error) {
	w.body.WriteString(s)
	return w.ResponseWriter.WriteString(s)
}

// CleanupExpiredKeys 清理过期的幂等键（可选，用于后台任务）
func (im *IdempotencyManager) CleanupExpiredKeys(prefix string) error {
	// Redis 会自动清理过期键，这里提供手动清理选项
	ctx := c.Request.Context()
	pattern := fmt.Sprintf("%s*", prefix)

	iter := im.redis.Scan(ctx, 0, pattern, 100).Iterator()
	for iter.Next(ctx) {
		key := iter.Val()
		ttl, err := im.redis.TTL(ctx, key).Result()
		if err != nil {
			continue
		}

		// 删除已过期或即将过期的键
		if ttl < 0 || ttl < time.Second {
			im.redis.Del(ctx, key)
		}
	}

	return iter.Err()
}
