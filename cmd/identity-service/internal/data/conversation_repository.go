package data

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// ConversationRepositoryImpl PostgreSQL实现
type ConversationRepositoryImpl struct {
	db  *sql.DB
	log *log.Helper
}

// NewConversationRepository 创建ConversationRepository实例
func NewConversationRepository(db *sql.DB, logger log.Logger) *ConversationRepositoryImpl {
	return &ConversationRepositoryImpl{
		db:  db,
		log: log.NewHelper(logger),
	}
}

// Conversation 对话模型
type Conversation struct {
	ID        string
	TenantID  string
	UserID    string
	Title     string
	Status    string // active, archived, deleted
	CreatedAt time.Time
	UpdatedAt time.Time
}

// CountByTenantID 统计租户的对话数
func (r *ConversationRepositoryImpl) CountByTenantID(ctx context.Context, tenantID string) (int64, error) {
	query := `SELECT COUNT(*) FROM conversations WHERE tenant_id = $1`

	var count int64
	if err := r.db.QueryRowContext(ctx, query, tenantID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count conversations: %w", err)
	}

	return count, nil
}

// CountActiveByTenantID 统计租户的活跃对话数
func (r *ConversationRepositoryImpl) CountActiveByTenantID(ctx context.Context, tenantID string) (int64, error) {
	query := `SELECT COUNT(*) FROM conversations WHERE tenant_id = $1 AND status = 'active'`

	var count int64
	if err := r.db.QueryRowContext(ctx, query, tenantID).Scan(&count); err != nil {
		return 0, fmt.Errorf("failed to count active conversations: %w", err)
	}

	return count, nil
}

// DeleteByTenantID 删除租户下的所有对话
func (r *ConversationRepositoryImpl) DeleteByTenantID(ctx context.Context, tenantID string) (int64, error) {
	// 使用事务确保数据一致性
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// 1. 删除对话中的消息
	messagesQuery := `
		DELETE FROM messages
		WHERE conversation_id IN (
			SELECT id FROM conversations WHERE tenant_id = $1
		)
	`
	messagesResult, err := tx.ExecContext(ctx, messagesQuery, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete messages: %w", err)
	}
	messagesCount, _ := messagesResult.RowsAffected()

	// 2. 删除对话
	conversationsQuery := `DELETE FROM conversations WHERE tenant_id = $1`
	conversationsResult, err := tx.ExecContext(ctx, conversationsQuery, tenantID)
	if err != nil {
		return 0, fmt.Errorf("failed to delete conversations: %w", err)
	}
	conversationsCount, _ := conversationsResult.RowsAffected()

	// 提交事务
	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("failed to commit transaction: %w", err)
	}

	r.log.Infof("Deleted %d conversations and %d messages for tenant %s",
		conversationsCount, messagesCount, tenantID)

	return conversationsCount, nil
}

// GetByID 根据ID获取对话
func (r *ConversationRepositoryImpl) GetByID(ctx context.Context, conversationID string) (*Conversation, error) {
	query := `
		SELECT id, tenant_id, user_id, title, status, created_at, updated_at
		FROM conversations
		WHERE id = $1
	`

	var conv Conversation
	if err := r.db.QueryRowContext(ctx, query, conversationID).Scan(
		&conv.ID,
		&conv.TenantID,
		&conv.UserID,
		&conv.Title,
		&conv.Status,
		&conv.CreatedAt,
		&conv.UpdatedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("conversation not found: %s", conversationID)
		}
		return nil, fmt.Errorf("failed to get conversation: %w", err)
	}

	return &conv, nil
}

// ListByTenant 列出租户的对话
func (r *ConversationRepositoryImpl) ListByTenant(ctx context.Context, tenantID string, offset, limit int) ([]*Conversation, error) {
	query := `
		SELECT id, tenant_id, user_id, title, status, created_at, updated_at
		FROM conversations
		WHERE tenant_id = $1
		ORDER BY updated_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.QueryContext(ctx, query, tenantID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to query conversations: %w", err)
	}
	defer rows.Close()

	conversations := make([]*Conversation, 0)
	for rows.Next() {
		var conv Conversation
		if err := rows.Scan(
			&conv.ID,
			&conv.TenantID,
			&conv.UserID,
			&conv.Title,
			&conv.Status,
			&conv.CreatedAt,
			&conv.UpdatedAt,
		); err != nil {
			r.log.Warnf("Failed to scan conversation row: %v", err)
			continue
		}
		conversations = append(conversations, &conv)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}

	return conversations, nil
}

// Create 创建对话
func (r *ConversationRepositoryImpl) Create(ctx context.Context, conv *Conversation) error {
	query := `
		INSERT INTO conversations (id, tenant_id, user_id, title, status, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	now := time.Now()
	if conv.CreatedAt.IsZero() {
		conv.CreatedAt = now
	}
	if conv.UpdatedAt.IsZero() {
		conv.UpdatedAt = now
	}

	_, err := r.db.ExecContext(ctx, query,
		conv.ID,
		conv.TenantID,
		conv.UserID,
		conv.Title,
		conv.Status,
		conv.CreatedAt,
		conv.UpdatedAt,
	)
	if err != nil {
		return fmt.Errorf("failed to create conversation: %w", err)
	}

	r.log.Infof("Created conversation: %s for tenant: %s", conv.ID, conv.TenantID)
	return nil
}
