package infrastructure

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-redis/redis/v8"
)

// ABTestCache A/B测试缓存
type ABTestCache struct {
	client *redis.Client
}

// NewABTestCache 创建A/B测试缓存
func NewABTestCache(client *redis.Client) *ABTestCache {
	return &ABTestCache{client: client}
}

// GetUserVariant 获取用户已分配的变体
func (c *ABTestCache) GetUserVariant(ctx context.Context, testID, userID string) (*domain.ABVariant, error) {
	key := fmt.Sprintf("ab_test:%s:user:%s:variant", testID, userID)

	data, err := c.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var variant domain.ABVariant
	if err := json.Unmarshal(data, &variant); err != nil {
		return nil, err
	}

	return &variant, nil
}

// SetUserVariant 设置用户分配的变体
func (c *ABTestCache) SetUserVariant(
	ctx context.Context,
	testID, userID string,
	variant *domain.ABVariant,
	ttl time.Duration,
) error {
	key := fmt.Sprintf("ab_test:%s:user:%s:variant", testID, userID)

	data, err := json.Marshal(variant)
	if err != nil {
		return err
	}

	return c.client.Set(ctx, key, data, ttl).Err()
}

// GetTest 获取测试配置（缓存）
func (c *ABTestCache) GetTest(ctx context.Context, testID string) (*domain.ABTestConfig, error) {
	key := fmt.Sprintf("ab_test:config:%s", testID)

	data, err := c.client.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var test domain.ABTestConfig
	if err := json.Unmarshal(data, &test); err != nil {
		return nil, err
	}

	return &test, nil
}

// SetTest 设置测试配置（缓存）
func (c *ABTestCache) SetTest(ctx context.Context, test *domain.ABTestConfig, ttl time.Duration) error {
	key := fmt.Sprintf("ab_test:config:%s", test.ID)

	data, err := json.Marshal(test)
	if err != nil {
		return err
	}

	return c.client.Set(ctx, key, data, ttl).Err()
}

// InvalidateTest 使测试配置缓存失效
func (c *ABTestCache) InvalidateTest(ctx context.Context, testID string) error {
	key := fmt.Sprintf("ab_test:config:%s", testID)
	return c.client.Del(ctx, key).Err()
}

// InvalidateUserVariant 使用户变体分配缓存失效
func (c *ABTestCache) InvalidateUserVariant(ctx context.Context, testID, userID string) error {
	key := fmt.Sprintf("ab_test:%s:user:%s:variant", testID, userID)
	return c.client.Del(ctx, key).Err()
}


