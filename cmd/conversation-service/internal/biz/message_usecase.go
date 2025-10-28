package biz

import (
	"context"

	"voicehelper/cmd/conversation-service/internal/domain"
)

// MessageUsecase 消息用例
type MessageUsecase struct {
	messageRepo      domain.MessageRepository
	conversationRepo domain.ConversationRepository
}

// NewMessageUsecase 创建消息用例
func NewMessageUsecase(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
) *MessageUsecase {
	return &MessageUsecase{
		messageRepo:      messageRepo,
		conversationRepo: conversationRepo,
	}
}

// SendMessage 发送消息
func (uc *MessageUsecase) SendMessage(
	ctx context.Context,
	conversationID string,
	userID string,
	role domain.MessageRole,
	content string,
) (*domain.Message, error) {
	// 1. 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	// 2. 检查权限（确保用户拥有该对话）
	if conversation.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	// 3. 检查是否可以发送消息
	if !conversation.CanSendMessage() {
		return nil, domain.ErrConversationLimitReached
	}

	// 4. 创建消息
	message := domain.NewMessage(
		conversationID,
		conversation.TenantID,
		userID,
		role,
		content,
	)

	// 5. 保存消息
	if err := uc.messageRepo.CreateMessage(ctx, message); err != nil {
		return nil, err
	}

	// 6. 更新对话
	conversation.IncrementMessageCount()
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		// 记录错误但不影响消息创建结果
		// TODO: 添加日志
	}

	return message, nil
}

// GetMessage 获取消息
func (uc *MessageUsecase) GetMessage(ctx context.Context, id string, userID string) (*domain.Message, error) {
	// 1. 获取消息
	message, err := uc.messageRepo.GetMessage(ctx, id)
	if err != nil {
		return nil, err
	}

	// 2. 检查权限（确保用户拥有该消息）
	if message.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	return message, nil
}

// ListMessages 列出消息
func (uc *MessageUsecase) ListMessages(
	ctx context.Context,
	conversationID string,
	userID string,
	limit int,
	offset int,
) ([]*domain.Message, int, error) {
	// 1. 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, 0, err
	}

	// 2. 检查权限（确保用户拥有该对话）
	if conversation.UserID != userID {
		return nil, 0, domain.ErrPermissionDenied
	}

	// 3. 列出消息
	return uc.messageRepo.ListMessages(ctx, conversationID, limit, offset)
}

// GetRecentMessages 获取最近的消息
func (uc *MessageUsecase) GetRecentMessages(
	ctx context.Context,
	conversationID string,
	userID string,
	limit int,
) ([]*domain.Message, error) {
	// 1. 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	// 2. 检查权限（确保用户拥有该对话）
	if conversation.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	// 3. 获取最近的消息
	return uc.messageRepo.GetRecentMessages(ctx, conversationID, limit)
}
