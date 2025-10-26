package domain

import "context"

// ConversationRepository 对话仓储接口
type ConversationRepository interface {
	// CreateConversation 创建对话
	CreateConversation(ctx context.Context, conversation *Conversation) error

	// GetConversation 获取对话
	GetConversation(ctx context.Context, id string) (*Conversation, error)

	// UpdateConversation 更新对话
	UpdateConversation(ctx context.Context, conversation *Conversation) error

	// ListConversations 列出对话
	ListConversations(ctx context.Context, tenantID, userID string, limit, offset int) ([]*Conversation, int, error)

	// DeleteConversation 删除对话
	DeleteConversation(ctx context.Context, id string) error
}

// MessageRepository 消息仓储接口
type MessageRepository interface {
	// CreateMessage 创建消息
	CreateMessage(ctx context.Context, message *Message) error

	// GetMessage 获取消息
	GetMessage(ctx context.Context, id string) (*Message, error)

	// ListMessages 列出消息
	ListMessages(ctx context.Context, conversationID string, limit, offset int) ([]*Message, int, error)

	// GetRecentMessages 获取最近的消息
	GetRecentMessages(ctx context.Context, conversationID string, limit int) ([]*Message, error)

	// DeleteMessages 删除消息
	DeleteMessages(ctx context.Context, conversationID string) error
}
