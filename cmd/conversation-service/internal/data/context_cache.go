package data

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voiceassistant/cmd/conversation-service/internal/domain"

	"github.com/go-redis/redis/v8"
)

const (
	// 上下文缓存键前缀
	contextCachePrefix = "context:"

	// 默认 TTL (24小时)
	defaultContextTTL = 24 * time.Hour

	// 最大上下文 Token 数
	maxContextTokens = 4000
)

// ContextCache 上下文缓存
type ContextCache struct {
	redis *redis.Client
}

// NewContextCache 创建上下文缓存
func NewContextCache(redis *redis.Client) *ContextCache {
	return &ContextCache{
		redis: redis,
	}
}

// GetContext 获取会话上下文
func (c *ContextCache) GetContext(ctx context.Context, conversationID string) (*domain.ConversationContext, error) {
	key := contextCachePrefix + conversationID
	data, err := c.redis.Get(ctx, key).Bytes()
	if err == redis.Nil {
		// 缓存未命中，返回空上下文
		return &domain.ConversationContext{
			ConversationID: conversationID,
			Messages:       []domain.ContextMessage{},
			CreatedAt:      time.Now(),
			UpdatedAt:      time.Now(),
		}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("redis get error: %w", err)
	}

	var context domain.ConversationContext
	if err := json.Unmarshal(data, &context); err != nil {
		return nil, fmt.Errorf("json unmarshal error: %w", err)
	}

	return &context, nil
}

// SetContext 设置会话上下文
func (c *ContextCache) SetContext(ctx context.Context, convContext *domain.ConversationContext, ttl time.Duration) error {
	if ttl == 0 {
		ttl = defaultContextTTL
	}

	// 自动截断上下文（基于 Token 数）
	convContext = c.truncateContext(convContext, maxContextTokens)

	key := contextCachePrefix + convContext.ConversationID
	data, err := json.Marshal(convContext)
	if err != nil {
		return fmt.Errorf("json marshal error: %w", err)
	}

	if err := c.redis.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("redis set error: %w", err)
	}

	return nil
}

// AppendMessage 追加消息到上下文
func (c *ContextCache) AppendMessage(ctx context.Context, conversationID string, message domain.ContextMessage) error {
	// 获取当前上下文
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("get context error: %w", err)
	}

	// 追加消息
	convContext.Messages = append(convContext.Messages, message)
	convContext.UpdatedAt = time.Now()
	convContext.MessageCount++
	convContext.TotalTokens += message.Tokens

	// 更新上下文
	if err := c.SetContext(ctx, convContext, defaultContextTTL); err != nil {
		return fmt.Errorf("set context error: %w", err)
	}

	return nil
}

// AppendMessages 批量追加消息
func (c *ContextCache) AppendMessages(ctx context.Context, conversationID string, messages []domain.ContextMessage) error {
	// 获取当前上下文
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return fmt.Errorf("get context error: %w", err)
	}

	// 批量追加
	for _, msg := range messages {
		convContext.Messages = append(convContext.Messages, msg)
		convContext.TotalTokens += msg.Tokens
	}
	convContext.MessageCount += len(messages)
	convContext.UpdatedAt = time.Now()

	// 更新上下文
	if err := c.SetContext(ctx, convContext, defaultContextTTL); err != nil {
		return fmt.Errorf("set context error: %w", err)
	}

	return nil
}

// DeleteContext 删除会话上下文
func (c *ContextCache) DeleteContext(ctx context.Context, conversationID string) error {
	key := contextCachePrefix + conversationID
	if err := c.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}
	return nil
}

// GetMessages 获取会话消息列表
func (c *ContextCache) GetMessages(ctx context.Context, conversationID string, limit int) ([]domain.ContextMessage, error) {
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	messages := convContext.Messages
	if limit > 0 && len(messages) > limit {
		// 返回最近的 N 条消息
		messages = messages[len(messages)-limit:]
	}

	return messages, nil
}

// GetContextSummary 获取上下文摘要
func (c *ContextCache) GetContextSummary(ctx context.Context, conversationID string) (*domain.ContextSummary, error) {
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	return &domain.ContextSummary{
		ConversationID: convContext.ConversationID,
		MessageCount:   convContext.MessageCount,
		TotalTokens:    convContext.TotalTokens,
		UserID:         convContext.UserID,
		TenantID:       convContext.TenantID,
		CreatedAt:      convContext.CreatedAt,
		UpdatedAt:      convContext.UpdatedAt,
	}, nil
}

// ClearContext 清空上下文（但保留基本信息）
func (c *ContextCache) ClearContext(ctx context.Context, conversationID string) error {
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return err
	}

	// 保留基本信息，清空消息
	convContext.Messages = []domain.ContextMessage{}
	convContext.MessageCount = 0
	convContext.TotalTokens = 0
	convContext.UpdatedAt = time.Now()

	return c.SetContext(ctx, convContext, defaultContextTTL)
}

// UpdateSystemPrompt 更新系统提示
func (c *ContextCache) UpdateSystemPrompt(ctx context.Context, conversationID string, systemPrompt string) error {
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return err
	}

	convContext.SystemPrompt = systemPrompt
	convContext.UpdatedAt = time.Now()

	return c.SetContext(ctx, convContext, defaultContextTTL)
}

// UpdateMetadata 更新元数据
func (c *ContextCache) UpdateMetadata(ctx context.Context, conversationID string, metadata map[string]string) error {
	convContext, err := c.GetContext(ctx, conversationID)
	if err != nil {
		return err
	}

	if convContext.Metadata == nil {
		convContext.Metadata = make(map[string]string)
	}

	for k, v := range metadata {
		convContext.Metadata[k] = v
	}
	convContext.UpdatedAt = time.Now()

	return c.SetContext(ctx, convContext, defaultContextTTL)
}

// ExtendTTL 延长上下文 TTL
func (c *ContextCache) ExtendTTL(ctx context.Context, conversationID string, ttl time.Duration) error {
	key := contextCachePrefix + conversationID
	if err := c.redis.Expire(ctx, key, ttl).Err(); err != nil {
		return fmt.Errorf("redis expire error: %w", err)
	}
	return nil
}

// GetTTL 获取上下文剩余 TTL
func (c *ContextCache) GetTTL(ctx context.Context, conversationID string) (time.Duration, error) {
	key := contextCachePrefix + conversationID
	ttl, err := c.redis.TTL(ctx, key).Result()
	if err != nil {
		return 0, fmt.Errorf("redis ttl error: %w", err)
	}
	return ttl, nil
}

// ========================================
// 上下文截断策略
// ========================================

// truncateContext 截断上下文（保持在 maxTokens 以内）
func (c *ContextCache) truncateContext(convContext *domain.ConversationContext, maxTokens int) *domain.ConversationContext {
	if convContext.TotalTokens <= maxTokens {
		return convContext
	}

	// 策略：保留系统消息 + 最近的消息
	var truncatedMessages []domain.ContextMessage
	currentTokens := 0

	// 从后往前遍历，保留最近的消息
	for i := len(convContext.Messages) - 1; i >= 0; i-- {
		msg := convContext.Messages[i]

		// 如果加上这条消息会超过限制，则停止
		if currentTokens+msg.Tokens > maxTokens {
			break
		}

		truncatedMessages = append([]domain.ContextMessage{msg}, truncatedMessages...)
		currentTokens += msg.Tokens
	}

	convContext.Messages = truncatedMessages
	convContext.TotalTokens = currentTokens

	return convContext
}

// ========================================
// 批量操作
// ========================================

// GetMultipleContexts 批量获取上下文
func (c *ContextCache) GetMultipleContexts(ctx context.Context, conversationIDs []string) (map[string]*domain.ConversationContext, error) {
	contexts := make(map[string]*domain.ConversationContext)

	for _, id := range conversationIDs {
		convContext, err := c.GetContext(ctx, id)
		if err != nil {
			return nil, fmt.Errorf("get context %s error: %w", id, err)
		}
		contexts[id] = convContext
	}

	return contexts, nil
}

// DeleteMultipleContexts 批量删除上下文
func (c *ContextCache) DeleteMultipleContexts(ctx context.Context, conversationIDs []string) error {
	keys := make([]string, len(conversationIDs))
	for i, id := range conversationIDs {
		keys[i] = contextCachePrefix + id
	}

	if err := c.redis.Del(ctx, keys...).Err(); err != nil {
		return fmt.Errorf("redis del error: %w", err)
	}

	return nil
}

// ========================================
// 统计与监控
// ========================================

// ContextStats 上下文统计
type ContextStats struct {
	TotalContexts   int64
	TotalMessages   int64
	TotalTokens     int64
	AverageTokens   float64
	AverageMessages float64
}

// GetStats 获取统计信息
func (c *ContextCache) GetStats(ctx context.Context) (*ContextStats, error) {
	// 获取所有上下文键
	keys, err := c.redis.Keys(ctx, contextCachePrefix+"*").Result()
	if err != nil {
		return nil, fmt.Errorf("redis keys error: %w", err)
	}

	stats := &ContextStats{
		TotalContexts: int64(len(keys)),
	}

	if len(keys) == 0 {
		return stats, nil
	}

	// 统计总消息数和总 Token 数
	for _, key := range keys {
		data, err := c.redis.Get(ctx, key).Bytes()
		if err != nil {
			continue
		}

		var convContext domain.ConversationContext
		if err := json.Unmarshal(data, &convContext); err != nil {
			continue
		}

		stats.TotalMessages += int64(convContext.MessageCount)
		stats.TotalTokens += int64(convContext.TotalTokens)
	}

	// 计算平均值
	if stats.TotalContexts > 0 {
		stats.AverageTokens = float64(stats.TotalTokens) / float64(stats.TotalContexts)
		stats.AverageMessages = float64(stats.TotalMessages) / float64(stats.TotalContexts)
	}

	return stats, nil
}

// CleanupExpiredContexts 清理过期上下文 (定时任务)
func (c *ContextCache) CleanupExpiredContexts(ctx context.Context) error {
	// Redis 会自动清理过期键，这里只是提供一个接口
	// 如果需要手动清理，可以遍历所有键并检查 TTL
	return nil
}
