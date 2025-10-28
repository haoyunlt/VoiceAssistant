package data

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"

	"voicehelper/cmd/conversation-service/internal/domain"
)

type contextRepo struct {
	redis *redis.Client
}

func NewContextRepository(rdb *redis.Client) domain.ContextRepository {
	return &contextRepo{redis: rdb}
}

// GetCached 获取缓存的上下文
func (r *contextRepo) GetCached(ctx context.Context, conversationID string) (*domain.ConversationContext, error) {
	key := "conversation:context:" + conversationID

	data, err := r.redis.Get(ctx, key).Bytes()
	if err == redis.Nil {
		// Not found
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	var convCtx domain.ConversationContext
	if err := json.Unmarshal(data, &convCtx); err != nil {
		return nil, err
	}

	return &convCtx, nil
}

// Cache 缓存上下文
func (r *contextRepo) Cache(ctx context.Context, context *domain.ConversationContext, ttl time.Duration) error {
	key := "conversation:context:" + context.ConversationID

	data, err := json.Marshal(context)
	if err != nil {
		return err
	}

	return r.redis.Set(ctx, key, data, ttl).Err()
}

// Invalidate 使缓存失效
func (r *contextRepo) Invalidate(ctx context.Context, conversationID string) error {
	key := "conversation:context:" + conversationID
	return r.redis.Del(ctx, key).Err()
}
