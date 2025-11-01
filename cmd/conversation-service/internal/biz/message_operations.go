package biz

import (
	"context"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/conversation-service/internal/domain"
)

// MessageOperations 消息操作服务
type MessageOperations struct {
	messageRepo      domain.MessageRepository
	conversationRepo domain.ConversationRepository
	logger           *log.Helper
	config           *MessageOperationsConfig
}

// MessageOperationsConfig 消息操作配置
type MessageOperationsConfig struct {
	AllowEdit       bool          // 是否允许编辑
	AllowDelete     bool          // 是否允许删除
	AllowRecall     bool          // 是否允许撤回
	EditTimeLimit   time.Duration // 编辑时间限制
	RecallTimeLimit time.Duration // 撤回时间限制
	SoftDelete      bool          // 软删除（标记为已删除）
}

// NewMessageOperations 创建消息操作服务
func NewMessageOperations(
	messageRepo domain.MessageRepository,
	conversationRepo domain.ConversationRepository,
	config *MessageOperationsConfig,
	logger log.Logger,
) *MessageOperations {
	if config == nil {
		config = &MessageOperationsConfig{
			AllowEdit:       true,
			AllowDelete:     true,
			AllowRecall:     true,
			EditTimeLimit:   15 * time.Minute,
			RecallTimeLimit: 2 * time.Minute,
			SoftDelete:      true,
		}
	}

	return &MessageOperations{
		messageRepo:      messageRepo,
		conversationRepo: conversationRepo,
		logger:           log.NewHelper(log.With(logger, "module", "message-operations")),
		config:           config,
	}
}

// EditMessage 编辑消息
func (m *MessageOperations) EditMessage(
	ctx context.Context,
	messageID, userID, newContent string,
) (*domain.Message, error) {
	if !m.config.AllowEdit {
		return nil, domain.ErrOperationNotAllowed
	}

	// 1. 获取消息
	message, err := m.messageRepo.GetMessage(ctx, messageID)
	if err != nil {
		return nil, err
	}

	// 2. 权限检查
	if message.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	// 3. 检查是否可编辑
	if !m.canEdit(message) {
		return nil, domain.ErrEditTimeExpired
	}

	// 4. 保存原始内容到历史
	if message.EditHistory == nil {
		message.EditHistory = make([]domain.MessageEdit, 0)
	}

	message.EditHistory = append(message.EditHistory, domain.MessageEdit{
		OriginalContent: message.Content,
		EditedAt:        time.Now(),
	})

	// 5. 更新内容
	message.Content = newContent
	message.UpdatedAt = time.Now()
	message.Edited = true
	message.EditCount++

	// 6. 保存到数据库
	if err := m.messageRepo.UpdateMessage(ctx, message); err != nil {
		return nil, fmt.Errorf("failed to update message: %w", err)
	}

	m.logger.Infof("Message edited: id=%s, user=%s, edit_count=%d",
		messageID, userID, message.EditCount)

	return message, nil
}

// DeleteMessage 删除消息
func (m *MessageOperations) DeleteMessage(
	ctx context.Context,
	messageID, userID string,
) error {
	if !m.config.AllowDelete {
		return domain.ErrOperationNotAllowed
	}

	// 1. 获取消息
	message, err := m.messageRepo.GetMessage(ctx, messageID)
	if err != nil {
		return err
	}

	// 2. 权限检查
	if message.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 3. 执行删除
	if m.config.SoftDelete {
		// 软删除：标记为已删除
		message.Status = "deleted"
		message.DeletedAt = time.Now()
		message.UpdatedAt = time.Now()

		if err := m.messageRepo.UpdateMessage(ctx, message); err != nil {
			return fmt.Errorf("failed to soft delete message: %w", err)
		}

		m.logger.Infof("Message soft deleted: id=%s, user=%s", messageID, userID)
	} else {
		// 硬删除：物理删除
		if err := m.messageRepo.DeleteMessage(ctx, messageID); err != nil {
			return fmt.Errorf("failed to delete message: %w", err)
		}

		m.logger.Infof("Message deleted: id=%s, user=%s", messageID, userID)
	}

	return nil
}

// RecallMessage 撤回消息
func (m *MessageOperations) RecallMessage(
	ctx context.Context,
	messageID, userID string,
) error {
	if !m.config.AllowRecall {
		return domain.ErrOperationNotAllowed
	}

	// 1. 获取消息
	message, err := m.messageRepo.GetMessage(ctx, messageID)
	if err != nil {
		return err
	}

	// 2. 权限检查
	if message.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 3. 检查是否可撤回
	if !m.canRecall(message) {
		return domain.ErrRecallTimeExpired
	}

	// 4. 标记为已撤回
	message.Status = "recalled"
	message.RecalledAt = time.Now()
	message.UpdatedAt = time.Now()

	// 5. 保存到数据库
	if err := m.messageRepo.UpdateMessage(ctx, message); err != nil {
		return fmt.Errorf("failed to recall message: %w", err)
	}

	m.logger.Infof("Message recalled: id=%s, user=%s", messageID, userID)

	return nil
}

// GetEditHistory 获取编辑历史
func (m *MessageOperations) GetEditHistory(
	ctx context.Context,
	messageID, userID string,
) ([]domain.MessageEdit, error) {
	// 1. 获取消息
	message, err := m.messageRepo.GetMessage(ctx, messageID)
	if err != nil {
		return nil, err
	}

	// 2. 权限检查
	if message.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	return message.EditHistory, nil
}

// canEdit 检查是否可编辑
func (m *MessageOperations) canEdit(message *domain.Message) bool {
	// 如果没有时间限制
	if m.config.EditTimeLimit == 0 {
		return true
	}

	// 检查是否超过编辑时间限制
	timeSinceCreation := time.Since(message.CreatedAt)
	return timeSinceCreation < m.config.EditTimeLimit
}

// canRecall 检查是否可撤回
func (m *MessageOperations) canRecall(message *domain.Message) bool {
	// 已经撤回的消息不能再撤回
	if message.Status == "recalled" || message.Status == "deleted" {
		return false
	}

	// 如果没有时间限制
	if m.config.RecallTimeLimit == 0 {
		return true
	}

	// 检查是否超过撤回时间限制
	timeSinceCreation := time.Since(message.CreatedAt)
	return timeSinceCreation < m.config.RecallTimeLimit
}

// BatchDeleteMessages 批量删除消息
func (m *MessageOperations) BatchDeleteMessages(
	ctx context.Context,
	messageIDs []string,
	userID string,
) error {
	if !m.config.AllowDelete {
		return domain.ErrOperationNotAllowed
	}

	for _, messageID := range messageIDs {
		if err := m.DeleteMessage(ctx, messageID, userID); err != nil {
			m.logger.Errorf("Failed to delete message %s: %v", messageID, err)
			// 继续处理其他消息
		}
	}

	return nil
}

// GetMessageStatus 获取消息状态信息
func (m *MessageOperations) GetMessageStatus(
	ctx context.Context,
	messageID, userID string,
) (*MessageStatus, error) {
	message, err := m.messageRepo.GetMessage(ctx, messageID)
	if err != nil {
		return nil, err
	}

	// 权限检查
	if message.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	status := &MessageStatus{
		MessageID:     messageID,
		Status:        message.Status,
		CanEdit:       m.canEdit(message),
		CanRecall:     m.canRecall(message),
		CanDelete:     m.config.AllowDelete,
		Edited:        message.Edited,
		EditCount:     message.EditCount,
		CreatedAt:     message.CreatedAt,
		UpdatedAt:     message.UpdatedAt,
	}

	if !message.RecalledAt.IsZero() {
		status.RecalledAt = &message.RecalledAt
	}

	if !message.DeletedAt.IsZero() {
		status.DeletedAt = &message.DeletedAt
	}

	// 计算剩余时间
	if m.config.EditTimeLimit > 0 && status.CanEdit {
		elapsed := time.Since(message.CreatedAt)
		remaining := m.config.EditTimeLimit - elapsed
		status.EditTimeRemaining = remaining
	}

	if m.config.RecallTimeLimit > 0 && status.CanRecall {
		elapsed := time.Since(message.CreatedAt)
		remaining := m.config.RecallTimeLimit - elapsed
		status.RecallTimeRemaining = remaining
	}

	return status, nil
}

// MessageStatus 消息状态
type MessageStatus struct {
	MessageID            string         `json:"message_id"`
	Status               string         `json:"status"`
	CanEdit              bool           `json:"can_edit"`
	CanRecall            bool           `json:"can_recall"`
	CanDelete            bool           `json:"can_delete"`
	Edited               bool           `json:"edited"`
	EditCount            int            `json:"edit_count"`
	EditTimeRemaining    time.Duration  `json:"edit_time_remaining,omitempty"`
	RecallTimeRemaining  time.Duration  `json:"recall_time_remaining,omitempty"`
	CreatedAt            time.Time      `json:"created_at"`
	UpdatedAt            time.Time      `json:"updated_at"`
	RecalledAt           *time.Time     `json:"recalled_at,omitempty"`
	DeletedAt            *time.Time     `json:"deleted_at,omitempty"`
}

