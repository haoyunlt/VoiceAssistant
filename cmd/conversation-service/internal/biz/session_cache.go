package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"

	"voicehelper/cmd/conversation-service/internal/domain"
)

// SessionCache Redis会话缓存服务
type SessionCache struct {
	redis *redis.Client
	ttl   time.Duration
	log   *log.Helper
}

// NewSessionCache 创建会话缓存服务
func NewSessionCache(redis *redis.Client, ttl time.Duration, logger log.Logger) *SessionCache {
	return &SessionCache{
		redis: redis,
		ttl:   ttl,
		log:   log.NewHelper(log.With(logger, "module", "session-cache")),
	}
}

// SaveConversation 保存会话到Redis
func (s *SessionCache) SaveConversation(ctx context.Context, conversation *domain.Conversation) error {
	key := s.getConversationKey(conversation.ID)

	data, err := json.Marshal(conversation)
	if err != nil {
		return fmt.Errorf("failed to marshal conversation: %w", err)
	}

	if err := s.redis.Set(ctx, key, data, s.ttl).Err(); err != nil {
		return fmt.Errorf("failed to save conversation to redis: %w", err)
	}

	s.log.WithContext(ctx).Debugf("Saved conversation to Redis: %s", conversation.ID)

	return nil
}

// GetConversation 从Redis获取会话
func (s *SessionCache) GetConversation(ctx context.Context, conversationID string) (*domain.Conversation, error) {
	key := s.getConversationKey(conversationID)

	data, err := s.redis.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil, ErrConversationNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get conversation from redis: %w", err)
	}

	var conversation domain.Conversation
	if err := json.Unmarshal([]byte(data), &conversation); err != nil {
		return nil, fmt.Errorf("failed to unmarshal conversation: %w", err)
	}

	return &conversation, nil
}

// DeleteConversation 从Redis删除会话
func (s *SessionCache) DeleteConversation(ctx context.Context, conversationID string) error {
	key := s.getConversationKey(conversationID)

	if err := s.redis.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to delete conversation from redis: %w", err)
	}

	s.log.WithContext(ctx).Debugf("Deleted conversation from Redis: %s", conversationID)

	return nil
}

// UpdateActivity 更新会话活动时间
func (s *SessionCache) UpdateActivity(ctx context.Context, conversationID string) error {
	key := s.getConversationKey(conversationID)

	// 延长TTL
	if err := s.redis.Expire(ctx, key, s.ttl).Err(); err != nil {
		return fmt.Errorf("failed to update activity: %w", err)
	}

	return nil
}

// GetActiveConversations 获取活跃会话列表（用于用户）
func (s *SessionCache) GetActiveConversations(ctx context.Context, userID string) ([]string, error) {
	// 使用Set存储用户的活跃会话ID
	key := s.getUserSessionsKey(userID)

	conversationIDs, err := s.redis.SMembers(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get active conversations: %w", err)
	}

	return conversationIDs, nil
}

// AddUserSession 添加用户会话到活跃列表
func (s *SessionCache) AddUserSession(ctx context.Context, userID, conversationID string) error {
	key := s.getUserSessionsKey(userID)

	if err := s.redis.SAdd(ctx, key, conversationID).Err(); err != nil {
		return fmt.Errorf("failed to add user session: %w", err)
	}

	// 设置过期时间
	if err := s.redis.Expire(ctx, key, s.ttl).Err(); err != nil {
		return fmt.Errorf("failed to set expiry: %w", err)
	}

	return nil
}

// RemoveUserSession 从活跃列表移除用户会话
func (s *SessionCache) RemoveUserSession(ctx context.Context, userID, conversationID string) error {
	key := s.getUserSessionsKey(userID)

	if err := s.redis.SRem(ctx, key, conversationID).Err(); err != nil {
		return fmt.Errorf("failed to remove user session: %w", err)
	}

	return nil
}

// getConversationKey 生成会话Key
func (s *SessionCache) getConversationKey(conversationID string) string {
	return fmt.Sprintf("conversation:session:%s", conversationID)
}

// getUserSessionsKey 生成用户会话列表Key
func (s *SessionCache) getUserSessionsKey(userID string) string {
	return fmt.Sprintf("user:sessions:%s", userID)
}

// ErrConversationNotFound 会话未找到错误
var ErrConversationNotFound = fmt.Errorf("conversation not found in cache")

