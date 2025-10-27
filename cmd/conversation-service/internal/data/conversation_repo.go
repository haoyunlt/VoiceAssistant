package data

import (
	"context"
	"encoding/json"
	"time"
	"voiceassistant/cmd/conversation-service/internal/domain"

	"gorm.io/gorm"
)

// ConversationDO 对话数据对象
type ConversationDO struct {
	ID           string `gorm:"primaryKey"`
	TenantID     string `gorm:"index"`
	UserID       string `gorm:"index"`
	Title        string
	Mode         string
	Status       string
	ContextJSON  string `gorm:"type:jsonb"`
	MetadataJSON string `gorm:"type:jsonb"`
	CreatedAt    time.Time
	UpdatedAt    time.Time
	LastActiveAt time.Time
}

// TableName 指定表名
func (ConversationDO) TableName() string {
	return "conversation.conversations"
}

// ConversationRepository 对话仓储实现
type ConversationRepository struct {
	db *gorm.DB
}

// NewConversationRepository 创建对话仓储
func NewConversationRepository(db *gorm.DB) domain.ConversationRepository {
	return &ConversationRepository{
		db: db,
	}
}

// CreateConversation 创建对话
func (r *ConversationRepository) CreateConversation(ctx context.Context, conversation *domain.Conversation) error {
	do := r.toDataObject(conversation)
	return r.db.WithContext(ctx).Create(do).Error
}

// GetConversation 获取对话
func (r *ConversationRepository) GetConversation(ctx context.Context, id string) (*domain.Conversation, error) {
	var do ConversationDO
	if err := r.db.WithContext(ctx).Where("id = ? AND status != ?", id, string(domain.StatusDeleted)).First(&do).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrConversationNotFound
		}
		return nil, err
	}

	return r.toDomain(&do), nil
}

// UpdateConversation 更新对话
func (r *ConversationRepository) UpdateConversation(ctx context.Context, conversation *domain.Conversation) error {
	do := r.toDataObject(conversation)
	return r.db.WithContext(ctx).Save(do).Error
}

// ListConversations 列出对话
func (r *ConversationRepository) ListConversations(ctx context.Context, tenantID, userID string, limit, offset int) ([]*domain.Conversation, int, error) {
	var dos []ConversationDO
	var total int64

	db := r.db.WithContext(ctx).Where("tenant_id = ? AND user_id = ? AND status != ?", tenantID, userID, string(domain.StatusDeleted))

	// 获取总数
	if err := db.Model(&ConversationDO{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// 分页查询
	if err := db.Order("last_active_at DESC").Limit(limit).Offset(offset).Find(&dos).Error; err != nil {
		return nil, 0, err
	}

	conversations := make([]*domain.Conversation, len(dos))
	for i, do := range dos {
		conversations[i] = r.toDomain(&do)
	}

	return conversations, int(total), nil
}

// DeleteConversation 删除对话
func (r *ConversationRepository) DeleteConversation(ctx context.Context, id string) error {
	return r.db.WithContext(ctx).Where("id = ?", id).Delete(&ConversationDO{}).Error
}

// toDataObject 转换为数据对象
func (r *ConversationRepository) toDataObject(conversation *domain.Conversation) *ConversationDO {
	contextJSON, err := json.Marshal(conversation.Context)
	if err != nil {
		// 记录错误但不中断，使用空 JSON
		contextJSON = []byte("{}")
	}

	metadataJSON, err := json.Marshal(conversation.Metadata)
	if err != nil {
		// 记录错误但不中断，使用空 JSON
		metadataJSON = []byte("{}")
	}

	return &ConversationDO{
		ID:           conversation.ID,
		TenantID:     conversation.TenantID,
		UserID:       conversation.UserID,
		Title:        conversation.Title,
		Mode:         string(conversation.Mode),
		Status:       string(conversation.Status),
		ContextJSON:  string(contextJSON),
		MetadataJSON: string(metadataJSON),
		CreatedAt:    conversation.CreatedAt,
		UpdatedAt:    conversation.UpdatedAt,
		LastActiveAt: conversation.LastActiveAt,
	}
}

// toDomain 转换为领域对象
func (r *ConversationRepository) toDomain(do *ConversationDO) *domain.Conversation {
	var context domain.ConversationContext
	if do.ContextJSON != "" && do.ContextJSON != "{}" {
		if err := json.Unmarshal([]byte(do.ContextJSON), &context); err != nil {
			// 记录错误并使用空上下文
			context = domain.ConversationContext{}
		}
	}

	var metadata map[string]string
	if do.MetadataJSON != "" && do.MetadataJSON != "{}" {
		if err := json.Unmarshal([]byte(do.MetadataJSON), &metadata); err != nil {
			// 记录错误并使用空 metadata
			metadata = make(map[string]string)
		}
	}
	if metadata == nil {
		metadata = make(map[string]string)
	}

	return &domain.Conversation{
		ID:           do.ID,
		TenantID:     do.TenantID,
		UserID:       do.UserID,
		Title:        do.Title,
		Mode:         domain.ConversationMode(do.Mode),
		Status:       domain.ConversationStatus(do.Status),
		Context:      &context,
		Metadata:     metadata,
		CreatedAt:    do.CreatedAt,
		UpdatedAt:    do.UpdatedAt,
		LastActiveAt: do.LastActiveAt,
	}
}
