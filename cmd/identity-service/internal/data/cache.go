package data

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	"voiceassistant/cmd/identity-service/internal/domain"
)

const (
	// 缓存键前缀
	userCachePrefix       = "user:"
	tenantCachePrefix     = "tenant:"
	permissionCachePrefix = "permission:"
	tokenCachePrefix      = "token:"

	// 默认 TTL
	defaultUserTTL       = 1 * time.Hour
	defaultTenantTTL     = 1 * time.Hour
	defaultPermissionTTL = 10 * time.Minute
	defaultTokenTTL      = 24 * time.Hour
)

// UserCache 用户缓存
type UserCache struct {
	redis *redis.Client
}

// NewUserCache 创建用户缓存
func NewUserCache(redis *redis.Client) *UserCache {
	return &UserCache{
		redis: redis,
	}
}

// GetUser 获取用户缓存
func (c *UserCache) GetUser(ctx context.Context, id string) (*domain.User, error) {
	key := userCachePrefix + id
	data, err := c.redis.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, nil // 缓存未命中
	}
	if err != nil {
		return nil, fmt.Errorf("redis get error: %w", err)
	}

	var user domain.User
	if err := json.Unmarshal(data, &user); err != nil {
		return nil, fmt.Errorf("json unmarshal error: %w", err)
	}

	return &user, nil
}

// SetUser 设置用户缓存
func (c *UserCache) SetUser(ctx context.Context, user *domain.User, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultUserTTL
	}

	key := userCachePrefix + user.ID
	data, err := json.Marshal(user)
	if err != nil {
		return fmt.Errorf("json marshal error: %w", err)
	}

	if err := c.redis.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("redis set error: %w", err)
	}

	return nil
}

// DeleteUser 删除用户缓存
func (c *UserCache) DeleteUser(ctx context.Context, id string) error {
	key := userCachePrefix + id
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}
	return nil
}

// GetUserByEmail 通过邮箱获取用户 (使用二级索引)
func (c *UserCache) GetUserByEmail(ctx context.Context, email string) (*domain.User, error) {
	// 从二级索引获取用户 ID
	indexKey := "user:email:" + email
	userID, err := c.redis.Get(ctx, indexKey).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("redis get index error: %w", err)
	}

	// 通过用户 ID 获取用户信息
	return c.GetUser(ctx, userID)
}

// SetUserEmailIndex 设置用户邮箱索引
func (c *UserCache) SetUserEmailIndex(ctx context.Context, email, userID string, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultUserTTL
	}

	indexKey := "user:email:" + email
	if err := c.redis.Set(ctx, indexKey, userID, ttl).Err(); err != nil {
		return fmt.Errorf("redis set index error: %w", err)
	}

	return nil
}

// TenantCache 租户缓存
type TenantCache struct {
	redis *redis.Client
}

// NewTenantCache 创建租户缓存
func NewTenantCache(redis *redis.Client) *TenantCache {
	return &TenantCache{
		redis: redis,
	}
}

// GetTenant 获取租户缓存
func (c *TenantCache) GetTenant(ctx context.Context, id string) (*domain.Tenant, error) {
	key := tenantCachePrefix + id
	data, err := c.redis.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("redis get error: %w", err)
	}

	var tenant domain.Tenant
	if err := json.Unmarshal(data, &tenant); err != nil {
		return nil, fmt.Errorf("json unmarshal error: %w", err)
	}

	return &tenant, nil
}

// SetTenant 设置租户缓存
func (c *TenantCache) SetTenant(ctx context.Context, tenant *domain.Tenant, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultTenantTTL
	}

	key := tenantCachePrefix + tenant.ID
	data, err := json.Marshal(tenant)
	if err != nil {
		return fmt.Errorf("json marshal error: %w", err)
	}

	if err := c.redis.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("redis set error: %w", err)
	}

	return nil
}

// DeleteTenant 删除租户缓存
func (c *TenantCache) DeleteTenant(ctx context.Context, id string) error {
	key := tenantCachePrefix + id
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}
	return nil
}

// PermissionCache 权限缓存
type PermissionCache struct {
	redis *redis.Client
}

// NewPermissionCache 创建权限缓存
func NewPermissionCache(redis *redis.Client) *PermissionCache {
	return &PermissionCache{
		redis: redis,
	}
}

// GetUserPermissions 获取用户权限缓存
func (c *PermissionCache) GetUserPermissions(ctx context.Context, userID string) ([]string, error) {
	key := permissionCachePrefix + userID
	permissions, err := c.redis.SMembers(ctx, key).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("redis smembers error: %w", err)
	}

	return permissions, nil
}

// SetUserPermissions 设置用户权限缓存
func (c *PermissionCache) SetUserPermissions(ctx context.Context, userID string, permissions []string, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultPermissionTTL
	}

	key := permissionCachePrefix + userID

	// 删除旧权限
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}

	// 设置新权限
	if len(permissions) > 0 {
		members := make([]interface{}, len(permissions))
		for i, p := range permissions {
			members[i] = p
		}
		if err := c.redis.SAdd(ctx, key, members...).Err(); err != nil {
			return fmt.Errorf("redis sadd error: %w", err)
		}

		// 设置过期时间
		if err := c.redis.Expire(ctx, key, ttl).Err(); err != nil {
			return fmt.Errorf("redis expire error: %w", err)
		}
	}

	return nil
}

// DeleteUserPermissions 删除用户权限缓存
func (c *PermissionCache) DeleteUserPermissions(ctx context.Context, userID string) error {
	key := permissionCachePrefix + userID
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}
	return nil
}

// HasPermission 检查用户是否有指定权限
func (c *PermissionCache) HasPermission(ctx context.Context, userID string, permission string) (bool, error) {
	key := permissionCachePrefix + userID
	exists, err := c.redis.SIsMember(ctx, key, permission).Result()
	if err != nil {
		return false, fmt.Errorf("redis sismember error: %w", err)
	}

	return exists, nil
}

// TokenCache Token 缓存
type TokenCache struct {
	redis *redis.Client
}

// NewTokenCache 创建 Token 缓存
func NewTokenCache(redis *redis.Client) *TokenCache {
	return &TokenCache{
		redis: redis,
	}
}

// SetToken 设置 Token 缓存
func (c *TokenCache) SetToken(ctx context.Context, token string, userID string, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultTokenTTL
	}

	key := tokenCachePrefix + token
	if err := c.redis.Set(ctx, key, userID, ttl).Err(); err != nil {
		return fmt.Errorf("redis set error: %w", err)
	}

	return nil
}

// GetToken 获取 Token 缓存
func (c *TokenCache) GetToken(ctx context.Context, token string) (string, error) {
	key := tokenCachePrefix + token
	userID, err := c.redis.Get(ctx, key).Result()
	if err == redis.Nil {
		return "", nil
	}
	if err != nil {
		return "", fmt.Errorf("redis get error: %w", err)
	}

	return userID, nil
}

// DeleteToken 删除 Token 缓存
func (c *TokenCache) DeleteToken(ctx context.Context, token string) error {
	key := tokenCachePrefix + token
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}
	return nil
}

// BlacklistToken 将 Token 加入黑名单
func (c *TokenCache) BlacklistToken(ctx context.Context, token string, ttl time.Duration) error {
	key := "token:blacklist:" + token
	if err := c.redis.Set(ctx, key, "1", ttl).Err(); err != nil {
		return fmt.Errorf("redis set error: %w", err)
	}
	return nil
}

// IsTokenBlacklisted 检查 Token 是否在黑名单
func (c *TokenCache) IsTokenBlacklisted(ctx context.Context, token string) (bool, error) {
	key := "token:blacklist:" + token
	exists, err := c.redis.Exists(ctx, key).Result()
	if err != nil {
		return false, fmt.Errorf("redis exists error: %w", err)
	}

	return exists > 0, nil
}

// CacheManager 缓存管理器 (统一管理所有缓存)
type CacheManager struct {
	User       *UserCache
	Tenant     *TenantCache
	Permission *PermissionCache
	Token      *TokenCache
}

// NewCacheManager 创建缓存管理器
func NewCacheManager(redis *redis.Client) *CacheManager {
	return &CacheManager{
		User:       NewUserCache(redis),
		Tenant:     NewTenantCache(redis),
		Permission: NewPermissionCache(redis),
		Token:      NewTokenCache(redis),
	}
}

// ClearAll 清空所有缓存 (仅用于测试)
func (m *CacheManager) ClearAll(ctx context.Context) error {
	patterns := []string{
		userCachePrefix + "*",
		tenantCachePrefix + "*",
		permissionCachePrefix + "*",
		tokenCachePrefix + "*",
	}

	for _, pattern := range patterns {
		keys, err := m.User.redis.Keys(ctx, pattern).Result()
		if err != nil {
			return fmt.Errorf("redis keys error: %w", err)
		}

		if len(keys) > 0 {
			if err := m.User.redis.Del(ctx, keys...).Err(); err != nil {
				return fmt.Errorf("redis del error: %w", err)
			}
		}
	}

	return nil
}

// Stats 缓存统计信息
type CacheStats struct {
	UserCount       int64
	TenantCount     int64
	PermissionCount int64
	TokenCount      int64
}

// GetStats 获取缓存统计信息
func (m *CacheManager) GetStats(ctx context.Context) (*CacheStats, error) {
	stats := &CacheStats{}

	// 统计用户缓存数量
	userKeys, err := m.User.redis.Keys(ctx, userCachePrefix+"*").Result()
	if err != nil {
		return nil, fmt.Errorf("redis keys error: %w", err)
	}
	stats.UserCount = int64(len(userKeys))

	// 统计租户缓存数量
	tenantKeys, err := m.Tenant.redis.Keys(ctx, tenantCachePrefix+"*").Result()
	if err != nil {
		return nil, fmt.Errorf("redis keys error: %w", err)
	}
	stats.TenantCount = int64(len(tenantKeys))

	// 统计权限缓存数量
	permKeys, err := m.Permission.redis.Keys(ctx, permissionCachePrefix+"*").Result()
	if err != nil {
		return nil, fmt.Errorf("redis keys error: %w", err)
	}
	stats.PermissionCount = int64(len(permKeys))

	// 统计 Token 缓存数量
	tokenKeys, err := m.Token.redis.Keys(ctx, tokenCachePrefix+"*").Result()
	if err != nil {
		return nil, fmt.Errorf("redis keys error: %w", err)
	}
	stats.TokenCount = int64(len(tokenKeys))

	return stats, nil
}
