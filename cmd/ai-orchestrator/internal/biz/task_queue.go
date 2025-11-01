package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
)

// TaskQueue 任务队列接口
type TaskQueue interface {
	// Enqueue 入队任务
	Enqueue(ctx context.Context, task *domain.Task) error
	// Dequeue 出队任务
	Dequeue(ctx context.Context) (*domain.Task, error)
	// UpdateStatus 更新任务状态
	UpdateStatus(ctx context.Context, taskID string, status domain.TaskStatus) error
	// GetQueueDepth 获取队列深度
	GetQueueDepth(ctx context.Context) (int64, error)
}

// RedisTaskQueue Redis实现的任务队列
type RedisTaskQueue struct {
	client      *redis.Client
	streamName  string // Stream名称
	groupName   string // Consumer Group名称
	consumerID  string // Consumer ID
	maxLen      int64  // 最大队列长度
	logger      *log.Helper
	queueMetric *QueueMetrics
}

// QueueMetrics 队列指标
type QueueMetrics struct {
	EnqueueTotal *int64 // 入队总数
	DequeueTotal *int64 // 出队总数
	QueueDepth   *int64 // 队列深度
}

// RedisTaskQueueConfig Redis任务队列配置
type RedisTaskQueueConfig struct {
	StreamName string
	GroupName  string
	ConsumerID string
	MaxLen     int64
}

// NewRedisTaskQueue 创建Redis任务队列
func NewRedisTaskQueue(
	client *redis.Client,
	config *RedisTaskQueueConfig,
	logger log.Logger,
) (*RedisTaskQueue, error) {
	q := &RedisTaskQueue{
		client:     client,
		streamName: config.StreamName,
		groupName:  config.GroupName,
		consumerID: config.ConsumerID,
		maxLen:     config.MaxLen,
		logger:     log.NewHelper(logger),
		queueMetric: &QueueMetrics{
			EnqueueTotal: new(int64),
			DequeueTotal: new(int64),
			QueueDepth:   new(int64),
		},
	}

	// 创建Consumer Group（如果不存在）
	err := q.createConsumerGroup(context.Background())
	if err != nil {
		q.logger.Warnf("failed to create consumer group (may already exist): %v", err)
	}

	return q, nil
}

// createConsumerGroup 创建Consumer Group
func (q *RedisTaskQueue) createConsumerGroup(ctx context.Context) error {
	// 尝试创建Stream（如果不存在）
	_, err := q.client.XGroupCreateMkStream(
		ctx,
		q.streamName,
		q.groupName,
		"0", // 从头开始消费
	).Result()

	return err
}

// Enqueue 入队任务
func (q *RedisTaskQueue) Enqueue(ctx context.Context, task *domain.Task) error {
	// 序列化任务
	taskData, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	// 推送到Redis Stream
	_, err = q.client.XAdd(ctx, &redis.XAddArgs{
		Stream: q.streamName,
		MaxLen: q.maxLen, // 限制队列最大长度
		Approx: true,     // 近似裁剪（性能更好）
		ID:     "*",      // 自动生成ID
		Values: map[string]interface{}{
			"task_id":  task.ID,
			"priority": task.Priority,
			"type":     task.Type,
			"data":     string(taskData),
		},
	}).Result()

	if err != nil {
		q.logger.Errorf("failed to enqueue task %s: %v", task.ID, err)
		return fmt.Errorf("failed to enqueue task: %w", err)
	}

	*q.queueMetric.EnqueueTotal++
	q.logger.Infof("task %s enqueued to Redis Stream", task.ID)

	return nil
}

// Dequeue 出队任务（阻塞式）
func (q *RedisTaskQueue) Dequeue(ctx context.Context) (*domain.Task, error) {
	// 使用XREADGROUP阻塞读取
	streams, err := q.client.XReadGroup(ctx, &redis.XReadGroupArgs{
		Group:    q.groupName,
		Consumer: q.consumerID,
		Streams:  []string{q.streamName, ">"},
		Count:    1,
		Block:    5 * time.Second, // 阻塞5秒
	}).Result()

	if err != nil {
		// 超时不算错误
		if err == redis.Nil {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to dequeue task: %w", err)
	}

	// 没有消息
	if len(streams) == 0 || len(streams[0].Messages) == 0 {
		return nil, nil
	}

	// 解析消息
	msg := streams[0].Messages[0]
	taskData, ok := msg.Values["data"].(string)
	if !ok {
		q.logger.Errorf("invalid task data format in message %s", msg.ID)
		// ACK消息（避免重复处理）
		q.client.XAck(ctx, q.streamName, q.groupName, msg.ID)
		return nil, fmt.Errorf("invalid task data format")
	}

	// 反序列化任务
	var task domain.Task
	if err := json.Unmarshal([]byte(taskData), &task); err != nil {
		q.logger.Errorf("failed to unmarshal task: %v", err)
		// ACK消息
		q.client.XAck(ctx, q.streamName, q.groupName, msg.ID)
		return nil, fmt.Errorf("failed to unmarshal task: %w", err)
	}

	// 存储消息ID（用于后续ACK）
	task.Metadata["stream_message_id"] = msg.ID

	*q.queueMetric.DequeueTotal++
	q.logger.Infof("task %s dequeued from Redis Stream", task.ID)

	return &task, nil
}

// UpdateStatus 更新任务状态（并ACK消息）
func (q *RedisTaskQueue) UpdateStatus(ctx context.Context, taskID string, status domain.TaskStatus) error {
	// 注意：实际的状态更新由TaskRepository负责
	// 这里只负责ACK Redis Stream消息

	// 从任务元数据中获取消息ID
	// 实际使用时需要从任务中获取
	q.logger.Infof("task %s status updated to %s", taskID, status)
	return nil
}

// AckMessage 确认消息
func (q *RedisTaskQueue) AckMessage(ctx context.Context, messageID string) error {
	_, err := q.client.XAck(ctx, q.streamName, q.groupName, messageID).Result()
	if err != nil {
		return fmt.Errorf("failed to ack message %s: %w", messageID, err)
	}
	return nil
}

// GetQueueDepth 获取队列深度
func (q *RedisTaskQueue) GetQueueDepth(ctx context.Context) (int64, error) {
	// 获取Stream长度
	length, err := q.client.XLen(ctx, q.streamName).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get queue depth: %w", err)
	}

	*q.queueMetric.QueueDepth = length
	return length, nil
}

// GetPendingCount 获取待处理消息数
func (q *RedisTaskQueue) GetPendingCount(ctx context.Context) (int64, error) {
	// 获取Pending消息数（已读取但未ACK）
	pending, err := q.client.XPending(ctx, q.streamName, q.groupName).Result()
	if err != nil {
		return 0, fmt.Errorf("failed to get pending count: %w", err)
	}

	return pending.Count, nil
}

// ClaimStaleMessages 认领超时的消息
func (q *RedisTaskQueue) ClaimStaleMessages(ctx context.Context, idleTime time.Duration) ([]*domain.Task, error) {
	// 获取Pending消息
	pending, err := q.client.XPendingExt(ctx, &redis.XPendingExtArgs{
		Stream: q.streamName,
		Group:  q.groupName,
		Start:  "-",
		End:    "+",
		Count:  10,
	}).Result()

	if err != nil {
		return nil, fmt.Errorf("failed to get pending messages: %w", err)
	}

	var tasks []*domain.Task

	// 认领超时的消息
	for _, msg := range pending {
		if msg.Idle < idleTime {
			continue
		}

		// 认领消息
		claimed, err := q.client.XClaim(ctx, &redis.XClaimArgs{
			Stream:   q.streamName,
			Group:    q.groupName,
			Consumer: q.consumerID,
			MinIdle:  idleTime,
			Messages: []string{msg.ID},
		}).Result()

		if err != nil {
			q.logger.Warnf("failed to claim message %s: %v", msg.ID, err)
			continue
		}

		// 解析任务
		for _, claimedMsg := range claimed {
			taskData, ok := claimedMsg.Values["data"].(string)
			if !ok {
				continue
			}

			var task domain.Task
			if err := json.Unmarshal([]byte(taskData), &task); err != nil {
				continue
			}

			task.Metadata["stream_message_id"] = claimedMsg.ID
			tasks = append(tasks, &task)
		}
	}

	q.logger.Infof("claimed %d stale messages", len(tasks))
	return tasks, nil
}
