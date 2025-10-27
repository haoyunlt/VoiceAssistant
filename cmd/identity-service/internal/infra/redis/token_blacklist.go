package redis

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

// TokenBlacklist Token黑名单
type TokenBlacklist struct {
	redisClient *redis.Client
	keyPrefix   string
}

// NewTokenBlacklist 创建Token黑名单
func NewTokenBlacklist(redisClient *redis.Client) *TokenBlacklist {
	return &TokenBlacklist{
		redisClient: redisClient,
		keyPrefix:   "token:blacklist",
	}
}

// Add 添加Token到黑名单
func (tb *TokenBlacklist) Add(ctx context.Context, token string, expiresIn time.Duration) error {
	key := fmt.Sprintf("%s:%s", tb.keyPrefix, token)
	return tb.redisClient.Set(ctx, key, "1", expiresIn).Err()
}

// IsBlacklisted 检查Token是否在黑名单中
func (tb *TokenBlacklist) IsBlacklisted(ctx context.Context, token string) (bool, error) {
	key := fmt.Sprintf("%s:%s", tb.keyPrefix, token)
	exists, err := tb.redisClient.Exists(ctx, key).Result()
	if err != nil {
		return false, err
	}
	return exists > 0, nil
}

// Remove 从黑名单中移除Token（通常不需要，因为会自动过期）
func (tb *TokenBlacklist) Remove(ctx context.Context, token string) error {
	key := fmt.Sprintf("%s:%s", tb.keyPrefix, token)
	return tb.redisClient.Del(ctx, key).Err()
}

// AddBatch 批量添加Token到黑名单
func (tb *TokenBlacklist) AddBatch(ctx context.Context, tokens []string, expiresIn time.Duration) error {
	pipe := tb.redisClient.Pipeline()

	for _, token := range tokens {
		key := fmt.Sprintf("%s:%s", tb.keyPrefix, token)
		pipe.Set(ctx, key, "1", expiresIn)
	}

	_, err := pipe.Exec(ctx)
	return err
}
