package biz

import (
	"context"

	"github.com/go-kratos/kratos/v2/log"
)

// Conversation is the conversation model.
type Conversation struct {
	ID       string
	UserID   string
	TenantID string
	Mode     string // voice, text, multimodal
	Status   string
}

// Message is the message model.
type Message struct {
	ID             string
	ConversationID string
	Role           string // user, assistant, system
	Content        string
	Metadata       map[string]interface{}
}

// ConversationRepo is the conversation repository interface.
type ConversationRepo interface {
	CreateConversation(ctx context.Context, conv *Conversation) error
	GetConversation(ctx context.Context, id string) (*Conversation, error)
	AddMessage(ctx context.Context, msg *Message) error
	GetMessages(ctx context.Context, conversationID string, limit int) ([]*Message, error)
}

// ConversationUsecase is the conversation usecase.
type ConversationUsecase struct {
	repo ConversationRepo
	log  *log.Helper
}

// NewConversationUsecase creates a new conversation usecase.
func NewConversationUsecase(repo ConversationRepo, logger log.Logger) *ConversationUsecase {
	return &ConversationUsecase{
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// CreateConversation creates a new conversation.
func (uc *ConversationUsecase) CreateConversation(ctx context.Context, conv *Conversation) error {
	uc.log.WithContext(ctx).Infof("Creating conversation for user: %s", conv.UserID)
	return uc.repo.CreateConversation(ctx, conv)
}
