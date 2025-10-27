package data

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
)

// SessionRepositoryImpl Redis实现
type SessionRepositoryImpl struct {
	rdb *redis.Client
	log *log.Helper
}

// NewSessionRepository 创建SessionRepository实例
func NewSessionRepository(rdb *redis.Client, logger log.Logger) *SessionRepositoryImpl {
	return &SessionRepositoryImpl{
		rdb: rdb,
		log: log.NewHelper(logger),
	}
}

// Session 会话模型
type Session struct {
	ID        string    `json:"id"`
	TenantID  string    `json:"tenant_id"`
	UserID    string    `json:"user_id"`
	Token     string    `json:"token"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}

// CountActiveByTenantID 统计租户的活跃会话数
func (r *SessionRepositoryImpl) CountActiveByTenantID(ctx context.Context, tenantID string) (int64, error) {
	// 使用Redis扫描匹配租户的会话键
	pattern := fmt.Sprintf("session:tenant:%s:*", tenantID)

	iter := r.rdb.Scan(ctx, 0, pattern, 0).Iterator()
	count := int64(0)

	for iter.Next(ctx) {
		count++
	}

	if err := iter.Err(); err != nil {
		return 0, fmt.Errorf("failed to scan sessions: %w", err)
	}

	return count, nil
}

// TerminateAllByTenantID 终止租户的所有会话
func (r *SessionRepositoryImpl) TerminateAllByTenantID(ctx context.Context, tenantID string) error {
	// 扫描并删除所有租户会话
	pattern := fmt.Sprintf("session:tenant:%s:*", tenantID)

	iter := r.rdb.Scan(ctx, 0, pattern, 100).Iterator()
	keys := make([]string, 0)

	for iter.Next(ctx) {
		keys = append(keys, iter.Val())
	}

	if err := iter.Err(); err != nil {
		return fmt.Errorf("failed to scan sessions: %w", err)
	}

	if len(keys) == 0 {
		return nil
	}

	// 批量删除
	if err := r.rdb.Del(ctx, keys...).Err(); err != nil {
		return fmt.Errorf("failed to delete sessions: %w", err)
	}

	r.log.Infof("Terminated %d sessions for tenant %s", len(keys), tenantID)
	return nil
}

// Create 创建会话
func (r *SessionRepositoryImpl) Create(ctx context.Context, session *Session) error {
	key := fmt.Sprintf("session:tenant:%s:%s", session.TenantID, session.ID)

	data, err := json.Marshal(session)
	if err != nil {
		return fmt.Errorf("failed to marshal session: %w", err)
	}

	ttl := time.Until(session.ExpiresAt)
	if ttl <= 0 {
		return fmt.Errorf("session already expired")
	}

	if err := r.rdb.Set(ctx, key, data, ttl).Err(); err != nil {
		return fmt.Errorf("failed to set session: %w", err)
	}

	r.log.Infof("Created session: %s for tenant: %s", session.ID, session.TenantID)
	return nil
}

// GetByID 根据ID获取会话
func (r *SessionRepositoryImpl) GetByID(ctx context.Context, tenantID, sessionID string) (*Session, error) {
	key := fmt.Sprintf("session:tenant:%s:%s", tenantID, sessionID)

	data, err := r.rdb.Get(ctx, key).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, fmt.Errorf("session not found: %s", sessionID)
		}
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	var session Session
	if err := json.Unmarshal(data, &session); err != nil {
		return nil, fmt.Errorf("failed to unmarshal session: %w", err)
	}

	return &session, nil
}

// Delete 删除会话
func (r *SessionRepositoryImpl) Delete(ctx context.Context, tenantID, sessionID string) error {
	key := fmt.Sprintf("session:tenant:%s:%s", tenantID, sessionID)

	if err := r.rdb.Del(ctx, key).Err(); err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	r.log.Infof("Deleted session: %s for tenant: %s", sessionID, tenantID)
	return nil
}
