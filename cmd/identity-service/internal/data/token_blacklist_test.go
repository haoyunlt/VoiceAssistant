package data

import (
	"context"
	"testing"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
)

func TestTokenBlacklistService(t *testing.T) {
	// 创建测试用Redis客户端
	client := redis.NewClient(&redis.Options{
		Addr: "localhost:6379",
		DB:   1, // 使用测试数据库
	})

	// 测试连接
	ctx := context.Background()
	_, err := client.Ping(ctx).Result()
	if err != nil {
		t.Skip("Redis not available, skipping integration test")
	}

	defer client.FlushDB(ctx)

	logger := log.DefaultLogger
	service := NewTokenBlacklistService(client, logger)

	t.Run("AddToBlacklist", func(t *testing.T) {
		token := "test-token-123"
		expiresAt := time.Now().Add(1 * time.Hour)

		err := service.AddToBlacklist(ctx, token, expiresAt)
		assert.NoError(t, err)

		isBlacklisted, err := service.IsBlacklisted(ctx, token)
		assert.NoError(t, err)
		assert.True(t, isBlacklisted)
	})

	t.Run("IsBlacklisted_NotExists", func(t *testing.T) {
		token := "non-existent-token"

		isBlacklisted, err := service.IsBlacklisted(ctx, token)
		assert.NoError(t, err)
		assert.False(t, isBlacklisted)
	})

	t.Run("AddToBlacklist_ExpiredToken", func(t *testing.T) {
		token := "expired-token"
		expiresAt := time.Now().Add(-1 * time.Hour) // 已过期

		err := service.AddToBlacklist(ctx, token, expiresAt)
		assert.NoError(t, err)

		// 过期的Token不应该被添加
		isBlacklisted, err := service.IsBlacklisted(ctx, token)
		assert.NoError(t, err)
		assert.False(t, isBlacklisted)
	})

	t.Run("RemoveFromBlacklist", func(t *testing.T) {
		token := "remove-test-token"
		expiresAt := time.Now().Add(1 * time.Hour)

		err := service.AddToBlacklist(ctx, token, expiresAt)
		assert.NoError(t, err)

		err = service.RemoveFromBlacklist(ctx, token)
		assert.NoError(t, err)

		isBlacklisted, err := service.IsBlacklisted(ctx, token)
		assert.NoError(t, err)
		assert.False(t, isBlacklisted)
	})

	t.Run("GetBlacklistStats", func(t *testing.T) {
		// 添加几个Token
		for i := 0; i < 3; i++ {
			token := string(rune('a' + i)) + "-token"
			expiresAt := time.Now().Add(1 * time.Hour)
			err := service.AddToBlacklist(ctx, token, expiresAt)
			assert.NoError(t, err)
		}

		stats, err := service.GetBlacklistStats(ctx)
		assert.NoError(t, err)
		assert.NotNil(t, stats)
		assert.GreaterOrEqual(t, stats["total_tokens"].(int64), int64(3))
	})
}
