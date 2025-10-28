package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"

	ws "voicehelper/cmd/conversation-service/internal/websocket"
)

// SyncService 多设备同步服务
type SyncService struct {
	redis *redis.Client
	hub   *ws.Hub
	log   *log.Helper
}

// NewSyncService 创建同步服务
func NewSyncService(redis *redis.Client, hub *ws.Hub, logger log.Logger) *SyncService {
	return &SyncService{
		redis: redis,
		hub:   hub,
		log:   log.NewHelper(log.With(logger, "module", "sync-service")),
	}
}

// SyncEvent 同步事件
type SyncEvent struct {
	Type      string                 `json:"type"`
	Event     string                 `json:"event"`
	Data      map[string]interface{} `json:"data"`
	Timestamp int64                  `json:"timestamp"`
}

// SyncDevices 同步用户的所有设备
func (s *SyncService) SyncDevices(ctx context.Context, userID string, event string, data map[string]interface{}) error {
	// 1. 构建同步消息
	syncEvent := &SyncEvent{
		Type:      ws.MessageTypeSync,
		Event:     event,
		Data:      data,
		Timestamp: time.Now().Unix(),
	}

	msgBytes, err := json.Marshal(syncEvent)
	if err != nil {
		return fmt.Errorf("failed to marshal sync event: %w", err)
	}

	// 2. 广播给用户的所有设备
	if err := s.hub.SendToUser(userID, msgBytes); err != nil {
		s.log.Errorf("Failed to broadcast sync event: %v", err)
	}

	// 3. 保存到Redis（供离线设备同步）
	if err := s.saveSyncEvent(ctx, userID, syncEvent); err != nil {
		s.log.Warnf("Failed to save sync event to Redis: %v", err)
	}

	return nil
}

// GetPendingSyncEvents 获取待同步事件（用户上线时）
func (s *SyncService) GetPendingSyncEvents(ctx context.Context, userID string, lastSyncTime int64) ([]*SyncEvent, error) {
	key := s.getSyncKey(userID)

	// 获取所有事件
	events, err := s.redis.LRange(ctx, key, 0, -1).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get sync events: %w", err)
	}

	// 过滤出 lastSyncTime 之后的事件
	var result []*SyncEvent
	for _, eventStr := range events {
		var event SyncEvent
		if err := json.Unmarshal([]byte(eventStr), &event); err != nil {
			s.log.Warnf("Failed to unmarshal sync event: %v", err)
			continue
		}

		if event.Timestamp > lastSyncTime {
			result = append(result, &event)
		}
	}

	return result, nil
}

// ClearPendingSyncEvents 清除待同步事件
func (s *SyncService) ClearPendingSyncEvents(ctx context.Context, userID string, beforeTimestamp int64) error {
	key := s.getSyncKey(userID)

	// 获取所有事件
	events, err := s.redis.LRange(ctx, key, 0, -1).Result()
	if err != nil {
		return fmt.Errorf("failed to get sync events: %w", err)
	}

	// 删除旧事件
	for _, eventStr := range events {
		var event SyncEvent
		if err := json.Unmarshal([]byte(eventStr), &event); err != nil {
			continue
		}

		if event.Timestamp < beforeTimestamp {
			s.redis.LRem(ctx, key, 1, eventStr)
		}
	}

	return nil
}

// saveSyncEvent 保存同步事件到Redis
func (s *SyncService) saveSyncEvent(ctx context.Context, userID string, event *SyncEvent) error {
	key := s.getSyncKey(userID)

	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal sync event: %w", err)
	}

	// 添加到列表
	if err := s.redis.RPush(ctx, key, data).Err(); err != nil {
		return fmt.Errorf("failed to save sync event: %w", err)
	}

	// 设置过期时间（7天）
	if err := s.redis.Expire(ctx, key, 7*24*time.Hour).Err(); err != nil {
		return fmt.Errorf("failed to set expiry: %w", err)
	}

	// 限制列表长度（最多保留100个事件）
	if err := s.redis.LTrim(ctx, key, -100, -1).Err(); err != nil {
		return fmt.Errorf("failed to trim list: %w", err)
	}

	return nil
}

// getSyncKey 生成同步Key
func (s *SyncService) getSyncKey(userID string) string {
	return fmt.Sprintf("sync:events:%s", userID)
}

