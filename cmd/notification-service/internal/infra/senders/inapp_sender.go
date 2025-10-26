package senders

import (
	"context"
	"encoding/json"
	"log"

	"github.com/redis/go-redis/v9"

	"notification-service/internal/domain"
)

type InAppSender struct {
	redis *redis.Client
}

func NewInAppSender(rdb *redis.Client) *InAppSender {
	return &InAppSender{
		redis: rdb,
	}
}

func (s *InAppSender) Send(notification *domain.Notification) error {
	ctx := context.Background()

	// Store notification in Redis for in-app retrieval
	key := "notification:user:" + notification.UserID

	// Build notification data
	data := map[string]interface{}{
		"id":         notification.ID,
		"type":       notification.Type,
		"title":      notification.Title,
		"content":    notification.Content,
		"event_type": notification.EventType,
		"created_at": notification.CreatedAt,
		"data":       notification.Data,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	// Add to user's notification list (sorted set)
	score := float64(notification.CreatedAt.Unix())
	if err := s.redis.ZAdd(ctx, key, redis.Z{
		Score:  score,
		Member: jsonData,
	}).Err(); err != nil {
		log.Printf("Failed to store in-app notification: %v", err)
		return err
	}

	// Keep only last 100 notifications
	s.redis.ZRemRangeByRank(ctx, key, 0, -101)

	// Set expiration (30 days)
	s.redis.Expire(ctx, key, 30*24*3600)

	// Publish to user's channel for real-time updates
	channel := "notification:realtime:" + notification.UserID
	s.redis.Publish(ctx, channel, jsonData)

	log.Printf("In-app notification sent to user: %s", notification.UserID)
	return nil
}

