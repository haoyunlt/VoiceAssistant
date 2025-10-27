package service

import (
	"context"

	"voiceassistant/cmd/conversation-service/internal/biz"
	"voiceassistant/cmd/conversation-service/internal/domain"
)

// ConversationService 对话服务实现
type ConversationService struct {
	conversationUc *biz.ConversationUsecase
	messageUc      *biz.MessageUsecase
}

// NewConversationService 创建对话服务
func NewConversationService(
	conversationUc *biz.ConversationUsecase,
	messageUc *biz.MessageUsecase,
) *ConversationService {
	return &ConversationService{
		conversationUc: conversationUc,
		messageUc:      messageUc,
	}
}

// CreateConversation 创建对话
func (s *ConversationService) CreateConversation(ctx context.Context, tenantID, userID, title string, mode domain.ConversationMode) (*domain.Conversation, error) {
	return s.conversationUc.CreateConversation(ctx, tenantID, userID, title, mode)
}

// GetConversation 获取对话
func (s *ConversationService) GetConversation(ctx context.Context, id, userID string) (*domain.Conversation, error) {
	return s.conversationUc.GetConversation(ctx, id, userID)
}

// UpdateConversationTitle 更新对话标题
func (s *ConversationService) UpdateConversationTitle(ctx context.Context, id, userID, title string) error {
	return s.conversationUc.UpdateConversationTitle(ctx, id, userID, title)
}

// ArchiveConversation 归档对话
func (s *ConversationService) ArchiveConversation(ctx context.Context, id, userID string) error {
	return s.conversationUc.ArchiveConversation(ctx, id, userID)
}

// DeleteConversation 删除对话
func (s *ConversationService) DeleteConversation(ctx context.Context, id, userID string) error {
	return s.conversationUc.DeleteConversation(ctx, id, userID)
}

// ListConversations 列出对话
func (s *ConversationService) ListConversations(ctx context.Context, tenantID, userID string, limit, offset int) ([]*domain.Conversation, int, error) {
	return s.conversationUc.ListConversations(ctx, tenantID, userID, limit, offset)
}

// SendMessage 发送消息
func (s *ConversationService) SendMessage(ctx context.Context, conversationID, userID string, role domain.MessageRole, content string) (*domain.Message, error) {
	return s.messageUc.SendMessage(ctx, conversationID, userID, role, content)
}

// GetMessage 获取消息
func (s *ConversationService) GetMessage(ctx context.Context, id, userID string) (*domain.Message, error) {
	return s.messageUc.GetMessage(ctx, id, userID)
}

// ListMessages 列出消息
func (s *ConversationService) ListMessages(ctx context.Context, conversationID, userID string, limit, offset int) ([]*domain.Message, int, error) {
	return s.messageUc.ListMessages(ctx, conversationID, userID, limit, offset)
}

// GetRecentMessages 获取最近的消息
func (s *ConversationService) GetRecentMessages(ctx context.Context, conversationID, userID string, limit int) ([]*domain.Message, error) {
	return s.messageUc.GetRecentMessages(ctx, conversationID, userID, limit)
}
