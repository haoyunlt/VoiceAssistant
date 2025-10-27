package infrastructure

import (
	"context"
	"encoding/json"
	"fmt"
	"time"
	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
)

// ABTestCacheImpl Redis缓存实现
type ABTestCacheImpl struct {
	client *redis.Client
	log    *log.Helper
}

// NewABTestCache 创建A/B测试缓存
func NewABTestCache(client *redis.Client, logger log.Logger) *ABTestCacheImpl {
	return &ABTestCacheImpl{
		client: client,
		log:    log.NewHelper(logger),
	}
}

const (
	// 缓存key前缀
	testCachePrefix        = "abtest:test:"
	userVariantCachePrefix = "abtest:user_variant:"
)

// GetTest 获取测试配置
func (c *ABTestCacheImpl) GetTest(ctx context.Context, testID string) (*domain.ABTestConfig, error) {
	key := testCachePrefix + testID

	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil // 缓存未命中
		}
		c.log.Errorf("failed to get test from cache: %v", err)
		return nil, err
	}

	var test domain.ABTestConfig
	if err := json.Unmarshal([]byte(data), &test); err != nil {
		c.log.Errorf("failed to unmarshal test: %v", err)
		return nil, err
	}

	return &test, nil
}

// SetTest 设置测试配置
func (c *ABTestCacheImpl) SetTest(ctx context.Context, test *domain.ABTestConfig, ttl time.Duration) error {
	key := testCachePrefix + test.ID

	data, err := json.Marshal(test)
	if err != nil {
		c.log.Errorf("failed to marshal test: %v", err)
		return err
	}

	if err := c.client.Set(ctx, key, data, ttl).Err(); err != nil {
		c.log.Errorf("failed to set test in cache: %v", err)
		return err
	}

	c.log.Debugf("cached test %s with TTL %v", test.ID, ttl)
	return nil
}

// InvalidateTest 清除测试缓存
func (c *ABTestCacheImpl) InvalidateTest(ctx context.Context, testID string) error {
	key := testCachePrefix + testID

	if err := c.client.Del(ctx, key).Err(); err != nil {
		c.log.Errorf("failed to invalidate test cache: %v", err)
		return err
	}

	c.log.Debugf("invalidated test cache %s", testID)
	return nil
}

// GetUserVariant 获取用户已分配的变体
func (c *ABTestCacheImpl) GetUserVariant(ctx context.Context, testID, userID string) (*domain.ABVariant, error) {
	key := c.userVariantKey(testID, userID)

	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			return nil, nil // 缓存未命中
		}
		c.log.Errorf("failed to get user variant from cache: %v", err)
		return nil, err
	}

	var variant domain.ABVariant
	if err := json.Unmarshal([]byte(data), &variant); err != nil {
		c.log.Errorf("failed to unmarshal variant: %v", err)
		return nil, err
	}

	return &variant, nil
}

// SetUserVariant 设置用户已分配的变体
func (c *ABTestCacheImpl) SetUserVariant(
	ctx context.Context,
	testID, userID string,
	variant *domain.ABVariant,
	ttl time.Duration,
) error {
	key := c.userVariantKey(testID, userID)

	data, err := json.Marshal(variant)
	if err != nil {
		c.log.Errorf("failed to marshal variant: %v", err)
		return err
	}

	if err := c.client.Set(ctx, key, data, ttl).Err(); err != nil {
		c.log.Errorf("failed to set user variant in cache: %v", err)
		return err
	}

	c.log.Debugf("cached user variant: test=%s, user=%s, variant=%s", testID, userID, variant.ID)
	return nil
}

// InvalidateUserVariant 清除用户变体缓存
func (c *ABTestCacheImpl) InvalidateUserVariant(ctx context.Context, testID, userID string) error {
	key := c.userVariantKey(testID, userID)

	if err := c.client.Del(ctx, key).Err(); err != nil {
		c.log.Errorf("failed to invalidate user variant cache: %v", err)
		return err
	}

	c.log.Debugf("invalidated user variant cache: test=%s, user=%s", testID, userID)
	return nil
}

// InvalidateTestUsers 清除测试下所有用户的变体缓存
func (c *ABTestCacheImpl) InvalidateTestUsers(ctx context.Context, testID string) error {
	pattern := c.userVariantKey(testID, "*")

	// 使用SCAN命令遍历匹配的key
	iter := c.client.Scan(ctx, 0, pattern, 100).Iterator()
	for iter.Next(ctx) {
		if err := c.client.Del(ctx, iter.Val()).Err(); err != nil {
			c.log.Errorf("failed to delete key %s: %v", iter.Val(), err)
		}
	}

	if err := iter.Err(); err != nil {
		c.log.Errorf("scan error: %v", err)
		return err
	}

	c.log.Debugf("invalidated all user variants for test %s", testID)
	return nil
}

// userVariantKey 生成用户变体缓存key
func (c *ABTestCacheImpl) userVariantKey(testID, userID string) string {
	return fmt.Sprintf("%s%s:%s", userVariantCachePrefix, testID, userID)
}

// GetCacheStats 获取缓存统计信息
func (c *ABTestCacheImpl) GetCacheStats(ctx context.Context) (map[string]interface{}, error) {
	// 统计测试配置缓存数量
	testKeys := c.client.Keys(ctx, testCachePrefix+"*").Val()
	testCount := len(testKeys)

	// 统计用户变体缓存数量
	variantKeys := c.client.Keys(ctx, userVariantCachePrefix+"*").Val()
	variantCount := len(variantKeys)

	// 获取Redis info
	info := c.client.Info(ctx, "stats").Val()

	return map[string]interface{}{
		"test_cache_count":    testCount,
		"variant_cache_count": variantCount,
		"redis_info":          info,
	}, nil
}

// Close 关闭连接
func (c *ABTestCacheImpl) Close() error {
	return c.client.Close()
}
