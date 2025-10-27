package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"

	"voiceassistant/cmd/conversation-service/internal/domain"
)

type contextRepo struct {
	redis *redis.Client
}

func NewContextRepository(rdb *redis.Client) domain.ContextRepository {
	return &contextRepo{redis: rdb}
}

func (r *contextRepo) Save(ctx context.Context, convCtx *domain.Context) error {
	key := "conversation:context:" + convCtx.ConversationID

	data, err := json.Marshal(convCtx)
	if err != nil {
		return err
	}

	// Cache for 24 hours
	return r.redis.Set(ctx, key, data, 24*time.Hour).Err()
}

func (r *contextRepo) GetByConversation(ctx context.Context, conversationID string) (*domain.Context, error) {
	key := "conversation:context:" + conversationID

	data, err := r.redis.Get(ctx, key).Bytes()
	if err == redis.Nil {
		// Not found, return empty context
		return &domain.Context{
			ConversationID: conversationID,
			Messages:       []domain.ContextMessage{},
			CreatedAt:      time.Now(),
			UpdatedAt:      time.Now(),
		}, nil
	}
	if err != nil {
		return nil, err
	}

	var convCtx domain.Context
	if err := json.Unmarshal(data, &convCtx); err != nil {
		return nil, err
	}

	return &convCtx, nil
}

func (r *contextRepo) Update(ctx context.Context, convCtx *domain.Context) error {
	convCtx.UpdatedAt = time.Now()
	return r.Save(ctx, convCtx)
}

func (r *contextRepo) Delete(ctx context.Context, conversationID string) error {
	key := "conversation:context:" + conversationID
	return r.redis.Del(ctx, key).Err()
}

func (r *contextRepo) AddMessage(ctx context.Context, conversationID string, msg domain.ContextMessage) error {
	convCtx, err := r.GetByConversation(ctx, conversationID)
	if err != nil {
		return err
	}

	convCtx.Messages = append(convCtx.Messages, msg)
	convCtx.TokenCount += msg.TokenCount
	convCtx.UpdatedAt = time.Now()

	return r.Update(ctx, convCtx)
}

func (r *contextRepo) Clear(ctx context.Context, conversationID string) error {
	convCtx := &domain.Context{
		ConversationID: conversationID,
		Messages:       []domain.ContextMessage{},
		TokenCount:     0,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}
	return r.Save(ctx, convCtx)
}
