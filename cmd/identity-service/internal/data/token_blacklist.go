package data

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
)

// TokenBlacklistService Token黑名单服务
type TokenBlacklistService struct {
	redis  *redis.Client
	prefix string
	log    *log.Helper
}

// NewTokenBlacklistService 创建Token黑名单服务
func NewTokenBlacklistService(redisClient *redis.Client, logger log.Logger) *TokenBlacklistService {
	return &TokenBlacklistService{
		redis:  redisClient,
		prefix: "token:blacklist:",
		log:    log.NewHelper(logger),
	}
}

// hashToken 对Token进行哈希处理（避免存储原始Token）
func (s *TokenBlacklistService) hashToken(token string) string {
	hash := sha256.Sum256([]byte(token))
	return hex.EncodeToString(hash[:])
}

// AddToBlacklist 将Token添加到黑名单
func (s *TokenBlacklistService) AddToBlacklist(ctx context.Context, token string, expiresAt time.Time) error {
	tokenHash := s.hashToken(token)
	key := fmt.Sprintf("%s%s", s.prefix, tokenHash)

	// 计算TTL（到Token过期的时间）
	ttl := time.Until(expiresAt)
	if ttl <= 0 {
		// Token已过期，无需加入黑名单
		return nil
	}

	// 设置Redis键，值为加入黑名单的时间戳
	err := s.redis.Set(ctx, key, time.Now().Unix(), ttl).Err()
	if err != nil {
		s.log.WithContext(ctx).Errorf("Failed to add token to blacklist: %v", err)
		return fmt.Errorf("添加Token到黑名单失败: %w", err)
	}

	s.log.WithContext(ctx).Infof("Token added to blacklist, expires in %v", ttl)
	return nil
}

// IsBlacklisted 检查Token是否在黑名单中
func (s *TokenBlacklistService) IsBlacklisted(ctx context.Context, token string) (bool, error) {
	tokenHash := s.hashToken(token)
	key := fmt.Sprintf("%s%s", s.prefix, tokenHash)

	exists, err := s.redis.Exists(ctx, key).Result()
	if err != nil {
		s.log.WithContext(ctx).Errorf("Failed to check token blacklist: %v", err)
		return false, fmt.Errorf("检查Token黑名单失败: %w", err)
	}

	return exists > 0, nil
}

// RemoveFromBlacklist 从黑名单中移除Token（通常不需要，让其自动过期）
func (s *TokenBlacklistService) RemoveFromBlacklist(ctx context.Context, token string) error {
	tokenHash := s.hashToken(token)
	key := fmt.Sprintf("%s%s", s.prefix, tokenHash)

	err := s.redis.Del(ctx, key).Err()
	if err != nil {
		s.log.WithContext(ctx).Errorf("Failed to remove token from blacklist: %v", err)
		return fmt.Errorf("从黑名单移除Token失败: %w", err)
	}

	return nil
}

// GetBlacklistStats 获取黑名单统计信息
func (s *TokenBlacklistService) GetBlacklistStats(ctx context.Context) (map[string]interface{}, error) {
	pattern := fmt.Sprintf("%s*", s.prefix)

	var cursor uint64
	var count int64
	var totalTTL time.Duration

	for {
		keys, nextCursor, err := s.redis.Scan(ctx, cursor, pattern, 100).Result()
		if err != nil {
			return nil, fmt.Errorf("扫描黑名单失败: %w", err)
		}

		count += int64(len(keys))

		// 计算平均TTL
		for _, key := range keys {
			ttl, err := s.redis.TTL(ctx, key).Result()
			if err == nil && ttl > 0 {
				totalTTL += ttl
			}
		}

		cursor = nextCursor
		if cursor == 0 {
			break
		}
	}

	var avgTTL time.Duration
	if count > 0 {
		avgTTL = totalTTL / time.Duration(count)
	}

	return map[string]interface{}{
		"total_tokens":        count,
		"average_ttl_seconds": avgTTL.Seconds(),
	}, nil
}
