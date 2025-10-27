package data

import (
	"context"
	"encoding/json"
	"time"
	"voiceassistant/cmd/conversation-service/internal/domain"

	"gorm.io/gorm"
)

// MessageDO 消息数据对象
type MessageDO struct {
	ID             string `gorm:"primaryKey"`
	ConversationID string `gorm:"index"`
	TenantID       string `gorm:"index"`
	UserID         string `gorm:"index"`
	Role           string
	Content        string `gorm:"type:text"`
	ContentType    string
	Tokens         int
	Model          string
	Provider       string
	MetadataJSON   string `gorm:"type:jsonb"`
	CreatedAt      time.Time
}

// TableName 指定表名
func (MessageDO) TableName() string {
	return "conversation.messages"
}

// MessageRepository 消息仓储实现
type MessageRepository struct {
	db *gorm.DB
}

// NewMessageRepository 创建消息仓储
func NewMessageRepository(db *gorm.DB) domain.MessageRepository {
	return &MessageRepository{
		db: db,
	}
}

// CreateMessage 创建消息
func (r *MessageRepository) CreateMessage(ctx context.Context, message *domain.Message) error {
	do := r.toDataObject(message)
	return r.db.WithContext(ctx).Create(do).Error
}

// GetMessage 获取消息
func (r *MessageRepository) GetMessage(ctx context.Context, id string) (*domain.Message, error) {
	var do MessageDO
	if err := r.db.WithContext(ctx).Where("id = ?", id).First(&do).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrMessageNotFound
		}
		return nil, err
	}

	return r.toDomain(&do), nil
}

// ListMessages 列出消息
func (r *MessageRepository) ListMessages(ctx context.Context, conversationID string, limit, offset int) ([]*domain.Message, int, error) {
	var dos []MessageDO
	var total int64

	db := r.db.WithContext(ctx).Where("conversation_id = ?", conversationID)

	// 获取总数
	if err := db.Model(&MessageDO{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// 分页查询
	if err := db.Order("created_at ASC").Limit(limit).Offset(offset).Find(&dos).Error; err != nil {
		return nil, 0, err
	}

	messages := make([]*domain.Message, len(dos))
	for i, do := range dos {
		messages[i] = r.toDomain(&do)
	}

	return messages, int(total), nil
}

// GetRecentMessages 获取最近的消息
func (r *MessageRepository) GetRecentMessages(ctx context.Context, conversationID string, limit int) ([]*domain.Message, error) {
	var dos []MessageDO

	if err := r.db.WithContext(ctx).
		Where("conversation_id = ?", conversationID).
		Order("created_at DESC").
		Limit(limit).
		Find(&dos).Error; err != nil {
		return nil, err
	}

	// 反转顺序（最新的在后面）
	messages := make([]*domain.Message, len(dos))
	for i, do := range dos {
		messages[len(dos)-1-i] = r.toDomain(&do)
	}

	return messages, nil
}

// DeleteMessages 删除消息
func (r *MessageRepository) DeleteMessages(ctx context.Context, conversationID string) error {
	return r.db.WithContext(ctx).Where("conversation_id = ?", conversationID).Delete(&MessageDO{}).Error
}

// GetSystemMessages 获取系统消息
func (r *MessageRepository) GetSystemMessages(ctx context.Context, conversationID string) ([]*domain.Message, error) {
	var dos []MessageDO

	if err := r.db.WithContext(ctx).
		Where("conversation_id = ? AND role = ?", conversationID, string(domain.RoleSystem)).
		Order("created_at ASC").
		Find(&dos).Error; err != nil {
		return nil, err
	}

	messages := make([]*domain.Message, len(dos))
	for i, do := range dos {
		messages[i] = r.toDomain(&do)
	}

	return messages, nil
}

// GetMessagesByRole 根据角色获取消息
func (r *MessageRepository) GetMessagesByRole(ctx context.Context, conversationID string, role domain.MessageRole, limit int) ([]*domain.Message, error) {
	var dos []MessageDO

	query := r.db.WithContext(ctx).
		Where("conversation_id = ? AND role = ?", conversationID, string(role)).
		Order("created_at DESC")

	if limit > 0 {
		query = query.Limit(limit)
	}

	if err := query.Find(&dos).Error; err != nil {
		return nil, err
	}

	// 反转顺序（保持时间正序）
	messages := make([]*domain.Message, len(dos))
	for i, do := range dos {
		messages[len(dos)-1-i] = r.toDomain(&do)
	}

	return messages, nil
}

// GetMessagesByTenantAndRole 根据租户和角色获取消息（跨对话）
func (r *MessageRepository) GetMessagesByTenantAndRole(ctx context.Context, tenantID string, role domain.MessageRole, limit, offset int) ([]*domain.Message, int, error) {
	var dos []MessageDO
	var total int64

	db := r.db.WithContext(ctx).Where("tenant_id = ? AND role = ?", tenantID, string(role))

	// 获取总数
	if err := db.Model(&MessageDO{}).Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// 分页查询
	if err := db.Order("created_at DESC").Limit(limit).Offset(offset).Find(&dos).Error; err != nil {
		return nil, 0, err
	}

	messages := make([]*domain.Message, len(dos))
	for i, do := range dos {
		messages[i] = r.toDomain(&do)
	}

	return messages, int(total), nil
}

// CountMessagesByRole 统计角色消息数量
func (r *MessageRepository) CountMessagesByRole(ctx context.Context, conversationID string, role domain.MessageRole) (int, error) {
	var count int64

	if err := r.db.WithContext(ctx).
		Model(&MessageDO{}).
		Where("conversation_id = ? AND role = ?", conversationID, string(role)).
		Count(&count).Error; err != nil {
		return 0, err
	}

	return int(count), nil
}

// toDataObject 转换为数据对象
func (r *MessageRepository) toDataObject(message *domain.Message) *MessageDO {
	metadataJSON, err := json.Marshal(message.Metadata)
	if err != nil {
		// 记录错误但不中断，使用空 JSON
		metadataJSON = []byte("{}")
	}

	return &MessageDO{
		ID:             message.ID,
		ConversationID: message.ConversationID,
		TenantID:       message.TenantID,
		UserID:         message.UserID,
		Role:           string(message.Role),
		Content:        message.Content,
		ContentType:    string(message.ContentType),
		Tokens:         message.Tokens,
		Model:          message.Model,
		Provider:       message.Provider,
		MetadataJSON:   string(metadataJSON),
		CreatedAt:      message.CreatedAt,
	}
}

// toDomain 转换为领域对象
func (r *MessageRepository) toDomain(do *MessageDO) *domain.Message {
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

	return &domain.Message{
		ID:             do.ID,
		ConversationID: do.ConversationID,
		TenantID:       do.TenantID,
		UserID:         do.UserID,
		Role:           domain.MessageRole(do.Role),
		Content:        do.Content,
		ContentType:    domain.ContentType(do.ContentType),
		Tokens:         do.Tokens,
		Model:          do.Model,
		Provider:       do.Provider,
		Metadata:       metadata,
		CreatedAt:      do.CreatedAt,
	}
}
