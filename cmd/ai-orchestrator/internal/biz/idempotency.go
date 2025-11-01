package biz

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
)

// IdempotencyService 幂等性服务
type IdempotencyService struct {
	cache  *redis.Client
	ttl    time.Duration
	logger *log.Helper
}

// IdempotencyConfig 幂等性配置
type IdempotencyConfig struct {
	TTL time.Duration // 幂等键有效期（默认2小时）
}

// NewIdempotencyService 创建幂等性服务
func NewIdempotencyService(
	cache *redis.Client,
	config *IdempotencyConfig,
	logger log.Logger,
) *IdempotencyService {
	if config == nil {
		config = &IdempotencyConfig{
			TTL: 2 * time.Hour,
		}
	}

	return &IdempotencyService{
		cache:  cache,
		ttl:    config.TTL,
		logger: log.NewHelper(logger),
	}
}

// CheckOrCreate 检查或创建幂等键
// 返回：isNew（是否是新请求）, existingTaskID（已存在的任务ID）, error
func (s *IdempotencyService) CheckOrCreate(
	ctx context.Context,
	idempotencyKey string,
	taskID string,
) (isNew bool, existingTaskID string, err error) {
	key := s.buildKey(idempotencyKey)

	// 尝试设置幂等键（SETNX）
	success, err := s.cache.SetNX(ctx, key, taskID, s.ttl).Result()
	if err != nil {
		s.logger.Errorf("failed to set idempotency key: %v", err)
		return false, "", fmt.Errorf("failed to check idempotency: %w", err)
	}

	if success {
		// 新请求
		s.logger.Infof("idempotency key created: %s -> %s", idempotencyKey, taskID)
		return true, "", nil
	}

	// 幂等键已存在，返回原任务ID
	existingTaskID, err = s.cache.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			// 键不存在（过期了），重试
			return s.CheckOrCreate(ctx, idempotencyKey, taskID)
		}
		s.logger.Errorf("failed to get existing task ID: %v", err)
		return false, "", fmt.Errorf("failed to get existing task: %w", err)
	}

	s.logger.Infof("idempotency key exists: %s -> %s", idempotencyKey, existingTaskID)
	return false, existingTaskID, nil
}

// Delete 删除幂等键
func (s *IdempotencyService) Delete(ctx context.Context, idempotencyKey string) error {
	key := s.buildKey(idempotencyKey)
	_, err := s.cache.Del(ctx, key).Result()
	if err != nil {
		s.logger.Warnf("failed to delete idempotency key: %v", err)
		return err
	}
	return nil
}

// Exists 检查幂等键是否存在
func (s *IdempotencyService) Exists(ctx context.Context, idempotencyKey string) (bool, string, error) {
	key := s.buildKey(idempotencyKey)
	taskID, err := s.cache.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return false, "", nil
		}
		return false, "", err
	}
	return true, taskID, nil
}

// ExtendTTL 延长幂等键有效期
func (s *IdempotencyService) ExtendTTL(ctx context.Context, idempotencyKey string, ttl time.Duration) error {
	key := s.buildKey(idempotencyKey)
	_, err := s.cache.Expire(ctx, key, ttl).Result()
	if err != nil {
		s.logger.Warnf("failed to extend idempotency key TTL: %v", err)
		return err
	}
	return nil
}

// buildKey 构建Redis键
func (s *IdempotencyService) buildKey(idempotencyKey string) string {
	return fmt.Sprintf("idempotency:%s", idempotencyKey)
}

// GenerateIdempotencyKey 生成幂等键
// 基于用户ID、租户ID、内容、时间窗口生成唯一键
func GenerateIdempotencyKey(
	userID, tenantID, content string,
	timeWindow time.Duration, // 时间窗口（如1分钟）
) string {
	// 时间窗口取整（分钟级）
	timestamp := time.Now().Truncate(timeWindow).Unix()

	// 构建原始字符串
	raw := fmt.Sprintf("%s:%s:%s:%d", userID, tenantID, content, timestamp)

	// MD5哈希
	hash := md5.Sum([]byte(raw))
	return hex.EncodeToString(hash[:])
}

// GenerateIdempotencyKeyFromRequest 从请求生成幂等键
func GenerateIdempotencyKeyFromRequest(
	userID, tenantID, conversationID, content string,
) string {
	// 基于请求关键字段生成（1分钟时间窗口）
	return GenerateIdempotencyKey(
		userID,
		tenantID,
		fmt.Sprintf("%s:%s", conversationID, content),
		time.Minute,
	)
}

// IdempotencyMetrics 幂等性指标
type IdempotencyMetrics struct {
	CheckTotal      int64 // 检查总数
	NewRequestCount int64 // 新请求数
	DuplicateCount  int64 // 重复请求数
	ErrorCount      int64 // 错误数
}

// GetMetrics 获取指标（简化版，实际应使用Prometheus）
func (s *IdempotencyService) GetMetrics() *IdempotencyMetrics {
	// 实际实现应该使用Prometheus Counter
	return &IdempotencyMetrics{
		CheckTotal:      0,
		NewRequestCount: 0,
		DuplicateCount:  0,
		ErrorCount:      0,
	}
}

