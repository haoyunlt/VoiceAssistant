package biz

import (
	"context"
	"fmt"

	"voicehelper/cmd/conversation-service/internal/domain"
)

// ConversationUsecase 对话用例
type ConversationUsecase struct {
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
}

// NewConversationUsecase 创建对话用例
func NewConversationUsecase(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
) *ConversationUsecase {
	return &ConversationUsecase{
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
	}
}

// CreateConversation 创建对话
func (uc *ConversationUsecase) CreateConversation(ctx context.Context, tenantID, userID, title string, mode domain.ConversationMode) (*domain.Conversation, error) {
	// 创建对话
	conversation := domain.NewConversation(tenantID, userID, title, mode)

	// 保存到数据库
	if err := uc.conversationRepo.CreateConversation(ctx, conversation); err != nil {
		return nil, fmt.Errorf("failed to create conversation: %w", err)
	}

	return conversation, nil
}

// GetConversation 获取对话
func (uc *ConversationUsecase) GetConversation(ctx context.Context, id, userID string) (*domain.Conversation, error) {
	conversation, err := uc.conversationRepo.GetConversation(ctx, id)
	if err != nil {
		return nil, err
	}

	// 权限检查
	if conversation.UserID != userID {
		return nil, domain.ErrUnauthorized
	}

	return conversation, nil
}

// UpdateConversationTitle 更新对话标题
func (uc *ConversationUsecase) UpdateConversationTitle(ctx context.Context, id, userID, title string) error {
	// 获取对话
	conversation, err := uc.GetConversation(ctx, id, userID)
	if err != nil {
		return err
	}

	// 更新标题
	conversation.UpdateTitle(title)

	// 保存
	return uc.conversationRepo.UpdateConversation(ctx, conversation)
}

// ArchiveConversation 归档对话
func (uc *ConversationUsecase) ArchiveConversation(ctx context.Context, id, userID string) error {
	// 获取对话
	conversation, err := uc.GetConversation(ctx, id, userID)
	if err != nil {
		return err
	}

	// 归档
	if err := conversation.Archive(); err != nil {
		return err
	}

	// 保存
	return uc.conversationRepo.UpdateConversation(ctx, conversation)
}

// DeleteConversation 删除对话
func (uc *ConversationUsecase) DeleteConversation(ctx context.Context, id, userID string) error {
	// 获取对话
	conversation, err := uc.GetConversation(ctx, id, userID)
	if err != nil {
		return err
	}

	// 软删除
	conversation.Delete()

	// 保存
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return err
	}

	// 删除消息
	return uc.messageRepo.DeleteMessages(ctx, id)
}

// ListConversations 列出对话
func (uc *ConversationUsecase) ListConversations(ctx context.Context, tenantID, userID string, limit, offset int) ([]*domain.Conversation, int, error) {
	return uc.conversationRepo.ListConversations(ctx, tenantID, userID, limit, offset)
}
