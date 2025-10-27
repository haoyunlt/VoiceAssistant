package biz

import (
	"context"
	"fmt"

	"voiceassistant/cmd/conversation-service/internal/domain"
)

// MessageUsecase 消息用例
type MessageUsecase struct {
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
}

// NewMessageUsecase 创建消息用例
func NewMessageUsecase(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
) *MessageUsecase {
	return &MessageUsecase{
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
	}
}

// SendMessage 发送消息
func (uc *MessageUsecase) SendMessage(ctx context.Context, conversationID, userID string, role domain.MessageRole, content string) (*domain.Message, error) {
	// 获取对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	// 权限检查
	if conversation.UserID != userID {
		return nil, domain.ErrUnauthorized
	}

	// 检查是否可以发送消息
	if !conversation.CanSendMessage() {
		return nil, domain.ErrConversationFull
	}

	// 创建消息
	message := domain.NewMessage(conversationID, conversation.TenantID, userID, role, content)

	// 保存消息
	if err := uc.messageRepo.CreateMessage(ctx, message); err != nil {
		return nil, fmt.Errorf("failed to create message: %w", err)
	}

	// 更新对话统计
	conversation.IncrementMessageCount()
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return nil, err
	}

	return message, nil
}

// GetMessage 获取消息
func (uc *MessageUsecase) GetMessage(ctx context.Context, id, userID string) (*domain.Message, error) {
	message, err := uc.messageRepo.GetMessage(ctx, id)
	if err != nil {
		return nil, err
	}

	// 权限检查
	if message.UserID != userID {
		return nil, domain.ErrUnauthorized
	}

	return message, nil
}

// ListMessages 列出消息
func (uc *MessageUsecase) ListMessages(ctx context.Context, conversationID, userID string, limit, offset int) ([]*domain.Message, int, error) {
	// 获取对话并检查权限
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, 0, err
	}

	if conversation.UserID != userID {
		return nil, 0, domain.ErrUnauthorized
	}

	// 获取消息列表
	return uc.messageRepo.ListMessages(ctx, conversationID, limit, offset)
}

// GetRecentMessages 获取最近的消息
func (uc *MessageUsecase) GetRecentMessages(ctx context.Context, conversationID, userID string, limit int) ([]*domain.Message, error) {
	// 获取对话并检查权限
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	if conversation.UserID != userID {
		return nil, domain.ErrUnauthorized
	}

	// 获取最近消息
	return uc.messageRepo.GetRecentMessages(ctx, conversationID, limit)
}

// GetCompressedContext 获取压缩后的上下文
func (uc *MessageUsecase) GetCompressedContext(
	ctx context.Context,
	conversationID string,
	userID string,
	maxTokens int,
	compressionService *ContextCompressionService,
) ([]*domain.Message, error) {
	// 获取对话并检查权限
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	if conversation.UserID != userID {
		return nil, domain.ErrUnauthorized
	}

	// 获取所有消息
	messages, _, err := uc.messageRepo.ListMessages(ctx, conversationID, 1000, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to list messages: %w", err)
	}

	// 计算当前token总数
	currentTokens := 0
	for _, msg := range messages {
		currentTokens += msg.Tokens
		if msg.Tokens == 0 {
			// 估算
			currentTokens += len(msg.Content) / 3
		}
	}

	// 如果未超过限制，直接返回
	if currentTokens <= maxTokens {
		return messages, nil
	}

	// 压缩上下文
	compressed, err := compressionService.CompressContext(ctx, messages, currentTokens)
	if err != nil {
		return nil, fmt.Errorf("failed to compress context: %w", err)
	}

	return compressed, nil
}
