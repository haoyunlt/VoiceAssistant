package biz

import (
	"context"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
)

// QuotaManager 配额管理器
type QuotaManager struct {
	redis  *redis.Client
	logger *log.Helper
	config *QuotaConfig
}

// QuotaConfig 配额配置
type QuotaConfig struct {
	// 默认配额（免费用户）
	DefaultConversationsPerMonth int
	DefaultMessagesPerDay        int
	DefaultTokensPerMonth        int
	DefaultStorageGB             int

	// 高级配额（付费用户）
	PremiumConversationsPerMonth int
	PremiumMessagesPerDay        int
	PremiumTokensPerMonth        int
	PremiumStorageGB             int

	// 企业配额
	EnterpriseConversationsPerMonth int
	EnterpriseMessagesPerDay        int
	EnterpriseTokensPerMonth        int
	EnterpriseStorageGB             int
}

// TenantQuota 租户配额
type TenantQuota struct {
	TenantID string `json:"tenant_id"`
	Tier     string `json:"tier"` // free, premium, enterprise

	// 配额限制
	ConversationsPerMonth int `json:"conversations_per_month"`
	MessagesPerDay        int `json:"messages_per_day"`
	TokensPerMonth        int `json:"tokens_per_month"`
	StorageGB             int `json:"storage_gb"`

	// 当前使用量
	CurrentConversations int `json:"current_conversations"`
	CurrentMessages      int `json:"current_messages"`
	CurrentTokens        int `json:"current_tokens"`
	CurrentStorageGB     float64 `json:"current_storage_gb"`

	// 使用率
	ConversationsUsage float64 `json:"conversations_usage"`
	MessagesUsage      float64 `json:"messages_usage"`
	TokensUsage        float64 `json:"tokens_usage"`
	StorageUsage       float64 `json:"storage_usage"`

	// 时间信息
	PeriodStart time.Time `json:"period_start"`
	PeriodEnd   time.Time `json:"period_end"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// NewQuotaManager 创建配额管理器
func NewQuotaManager(redis *redis.Client, config *QuotaConfig, logger log.Logger) *QuotaManager {
	if config == nil {
		config = &QuotaConfig{
			// 免费用户
			DefaultConversationsPerMonth: 50,
			DefaultMessagesPerDay:        100,
			DefaultTokensPerMonth:        100000,
			DefaultStorageGB:             1,

			// 高级用户
			PremiumConversationsPerMonth: 500,
			PremiumMessagesPerDay:        1000,
			PremiumTokensPerMonth:        1000000,
			PremiumStorageGB:             10,

			// 企业用户
			EnterpriseConversationsPerMonth: -1, // 无限制
			EnterpriseMessagesPerDay:        -1,
			EnterpriseTokensPerMonth:        -1,
			EnterpriseStorageGB:             100,
		}
	}

	return &QuotaManager{
		redis:  redis,
		logger: log.NewHelper(log.With(logger, "module", "quota-manager")),
		config: config,
	}
}

// CheckQuota 检查配额是否足够
func (qm *QuotaManager) CheckQuota(
	ctx context.Context,
	tenantID string,
	resourceType string,
	amount int,
) (bool, error) {
	// 获取当前配额
	quota, err := qm.GetQuota(ctx, tenantID)
	if err != nil {
		return false, err
	}

	// 检查不同类型的配额
	switch resourceType {
	case "conversations":
		if quota.ConversationsPerMonth < 0 {
			return true, nil // 无限制
		}
		return quota.CurrentConversations+amount <= quota.ConversationsPerMonth, nil

	case "messages":
		if quota.MessagesPerDay < 0 {
			return true, nil
		}
		return quota.CurrentMessages+amount <= quota.MessagesPerDay, nil

	case "tokens":
		if quota.TokensPerMonth < 0 {
			return true, nil
		}
		return quota.CurrentTokens+amount <= quota.TokensPerMonth, nil

	default:
		return false, fmt.Errorf("unknown resource type: %s", resourceType)
	}
}

// ConsumeQuota 消费配额
func (qm *QuotaManager) ConsumeQuota(
	ctx context.Context,
	tenantID string,
	resourceType string,
	amount int,
) error {
	// 检查配额
	allowed, err := qm.CheckQuota(ctx, tenantID, resourceType, amount)
	if err != nil {
		return err
	}

	if !allowed {
		qm.logger.Warnf("Quota exceeded: tenant=%s, resource=%s, amount=%d",
			tenantID, resourceType, amount)
		return fmt.Errorf("quota exceeded for %s", resourceType)
	}

	// 增加使用量
	key := qm.getQuotaKey(tenantID, resourceType)
	if err := qm.redis.IncrBy(ctx, key, int64(amount)).Err(); err != nil {
		return fmt.Errorf("failed to increment quota: %w", err)
	}

	// 如果是首次使用，设置过期时间
	ttl, err := qm.redis.TTL(ctx, key).Result()
	if err == nil && ttl < 0 {
		// 根据资源类型设置不同的过期时间
		var expiration time.Duration
		switch resourceType {
		case "conversations", "tokens":
			expiration = qm.getMonthlyExpiration()
		case "messages":
			expiration = 24 * time.Hour
		}

		qm.redis.Expire(ctx, key, expiration)
	}

	qm.logger.Debugf("Quota consumed: tenant=%s, resource=%s, amount=%d",
		tenantID, resourceType, amount)

	return nil
}

// GetQuota 获取配额信息
func (qm *QuotaManager) GetQuota(ctx context.Context, tenantID string) (*TenantQuota, error) {
	// 获取租户等级
	tier, err := qm.getTenantTier(ctx, tenantID)
	if err != nil {
		tier = "free" // 默认免费
	}

	// 获取配额限制
	quota := &TenantQuota{
		TenantID: tenantID,
		Tier:     tier,
	}

	switch tier {
	case "premium":
		quota.ConversationsPerMonth = qm.config.PremiumConversationsPerMonth
		quota.MessagesPerDay = qm.config.PremiumMessagesPerDay
		quota.TokensPerMonth = qm.config.PremiumTokensPerMonth
		quota.StorageGB = qm.config.PremiumStorageGB

	case "enterprise":
		quota.ConversationsPerMonth = qm.config.EnterpriseConversationsPerMonth
		quota.MessagesPerDay = qm.config.EnterpriseMessagesPerDay
		quota.TokensPerMonth = qm.config.EnterpriseTokensPerMonth
		quota.StorageGB = qm.config.EnterpriseStorageGB

	default: // free
		quota.ConversationsPerMonth = qm.config.DefaultConversationsPerMonth
		quota.MessagesPerDay = qm.config.DefaultMessagesPerDay
		quota.TokensPerMonth = qm.config.DefaultTokensPerMonth
		quota.StorageGB = qm.config.DefaultStorageGB
	}

	// 获取当前使用量
	quota.CurrentConversations, _ = qm.getCurrentUsage(ctx, tenantID, "conversations")
	quota.CurrentMessages, _ = qm.getCurrentUsage(ctx, tenantID, "messages")
	quota.CurrentTokens, _ = qm.getCurrentUsage(ctx, tenantID, "tokens")

	// 计算使用率
	if quota.ConversationsPerMonth > 0 {
		quota.ConversationsUsage = float64(quota.CurrentConversations) / float64(quota.ConversationsPerMonth)
	}
	if quota.MessagesPerDay > 0 {
		quota.MessagesUsage = float64(quota.CurrentMessages) / float64(quota.MessagesPerDay)
	}
	if quota.TokensPerMonth > 0 {
		quota.TokensUsage = float64(quota.CurrentTokens) / float64(quota.TokensPerMonth)
	}

	// 设置周期时间
	now := time.Now()
	quota.PeriodStart = time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
	quota.PeriodEnd = quota.PeriodStart.AddDate(0, 1, 0).Add(-time.Second)
	quota.UpdatedAt = now

	return quota, nil
}

// SetTenantTier 设置租户等级
func (qm *QuotaManager) SetTenantTier(ctx context.Context, tenantID, tier string) error {
	key := fmt.Sprintf("tenant:tier:%s", tenantID)
	
	// 验证等级
	validTiers := map[string]bool{
		"free":       true,
		"premium":    true,
		"enterprise": true,
	}

	if !validTiers[tier] {
		return fmt.Errorf("invalid tier: %s", tier)
	}

	// 保存到 Redis
	if err := qm.redis.Set(ctx, key, tier, 0).Err(); err != nil {
		return fmt.Errorf("failed to set tenant tier: %w", err)
	}

	qm.logger.Infof("Tenant tier updated: tenant=%s, tier=%s", tenantID, tier)

	return nil
}

// ResetQuota 重置配额（手动操作）
func (qm *QuotaManager) ResetQuota(ctx context.Context, tenantID, resourceType string) error {
	key := qm.getQuotaKey(tenantID, resourceType)
	
	if err := qm.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to reset quota: %w", err)
	}

	qm.logger.Infof("Quota reset: tenant=%s, resource=%s", tenantID, resourceType)

	return nil
}

// GetQuotaAlerts 获取配额告警（使用率超过阈值）
func (qm *QuotaManager) GetQuotaAlerts(ctx context.Context, tenantID string, threshold float64) ([]string, error) {
	quota, err := qm.GetQuota(ctx, tenantID)
	if err != nil {
		return nil, err
	}

	alerts := make([]string, 0)

	if quota.ConversationsUsage >= threshold {
		alerts = append(alerts, fmt.Sprintf("Conversations quota at %.0f%%", quota.ConversationsUsage*100))
	}

	if quota.MessagesUsage >= threshold {
		alerts = append(alerts, fmt.Sprintf("Messages quota at %.0f%%", quota.MessagesUsage*100))
	}

	if quota.TokensUsage >= threshold {
		alerts = append(alerts, fmt.Sprintf("Tokens quota at %.0f%%", quota.TokensUsage*100))
	}

	return alerts, nil
}

// getQuotaKey 生成配额键
func (qm *QuotaManager) getQuotaKey(tenantID, resourceType string) string {
	now := time.Now()

	switch resourceType {
	case "messages":
		// 按天
		return fmt.Sprintf("quota:%s:%s:%s", tenantID, resourceType, now.Format("2006-01-02"))
	case "conversations", "tokens":
		// 按月
		return fmt.Sprintf("quota:%s:%s:%s", tenantID, resourceType, now.Format("2006-01"))
	default:
		return fmt.Sprintf("quota:%s:%s", tenantID, resourceType)
	}
}

// getTenantTier 获取租户等级
func (qm *QuotaManager) getTenantTier(ctx context.Context, tenantID string) (string, error) {
	key := fmt.Sprintf("tenant:tier:%s", tenantID)
	
	tier, err := qm.redis.Get(ctx, key).Result()
	if err == redis.Nil {
		return "free", nil // 默认免费
	}
	if err != nil {
		return "", err
	}

	return tier, nil
}

// getCurrentUsage 获取当前使用量
func (qm *QuotaManager) getCurrentUsage(ctx context.Context, tenantID, resourceType string) (int, error) {
	key := qm.getQuotaKey(tenantID, resourceType)
	
	count, err := qm.redis.Get(ctx, key).Int()
	if err == redis.Nil {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}

	return count, nil
}

// getMonthlyExpiration 获取月度过期时间
func (qm *QuotaManager) getMonthlyExpiration() time.Duration {
	now := time.Now()
	nextMonth := time.Date(now.Year(), now.Month()+1, 1, 0, 0, 0, 0, time.UTC)
	return time.Until(nextMonth)
}

