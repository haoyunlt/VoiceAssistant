package scheduler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

// TaskStatus 任务状态
type TaskStatus string

const (
	TaskStatusPending   TaskStatus = "pending"   // 等待执行
	TaskStatusScheduled TaskStatus = "scheduled" // 已调度
	TaskStatusRunning   TaskStatus = "running"   // 执行中
	TaskStatusCompleted TaskStatus = "completed" // 已完成
	TaskStatusFailed    TaskStatus = "failed"    // 执行失败
	TaskStatusCancelled TaskStatus = "cancelled" // 已取消
)

// TaskType 任务类型
type TaskType string

const (
	TaskTypeOneTime   TaskType = "one_time"  // 一次性任务
	TaskTypeRecurring TaskType = "recurring" // 重复任务
	TaskTypeDelayed   TaskType = "delayed"   // 延迟任务
)

// Task 定时任务
type Task struct {
	ID          string                 `json:"id"`
	Type        TaskType               `json:"type"`
	Status      TaskStatus             `json:"status"`
	Name        string                 `json:"name"`
	Payload     map[string]interface{} `json:"payload"`
	ScheduledAt time.Time              `json:"scheduled_at"`
	ExecutedAt  *time.Time             `json:"executed_at,omitempty"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`

	// 重复任务配置
	CronExpression string        `json:"cron_expression,omitempty"` // cron表达式
	Interval       time.Duration `json:"interval,omitempty"`        // 间隔时间
	MaxRetries     int           `json:"max_retries"`
	RetryCount     int           `json:"retry_count"`

	// 延迟任务配置
	DelaySeconds int `json:"delay_seconds,omitempty"`

	// 执行结果
	Result    interface{} `json:"result,omitempty"`
	Error     string      `json:"error,omitempty"`
	CreatedAt time.Time   `json:"created_at"`
	UpdatedAt time.Time   `json:"updated_at"`
}

// TaskQueue 任务队列
type TaskQueue struct {
	redis      *redis.Client
	handlers   map[string]TaskHandler
	mu         sync.RWMutex
	stopChan   chan struct{}
	wg         sync.WaitGroup
	maxWorkers int

	// Redis keys
	taskQueueKey  string // Sorted Set: 存储待执行任务
	taskDataKey   string // Hash: 存储任务数据
	processingKey string // Set: 正在执行的任务
	completedKey  string // List: 已完成任务记录
}

// TaskHandler 任务处理函数
type TaskHandler func(ctx context.Context, task *Task) error

// NewTaskQueue 创建任务队列
func NewTaskQueue(redisClient *redis.Client, maxWorkers int) *TaskQueue {
	return &TaskQueue{
		redis:         redisClient,
		handlers:      make(map[string]TaskHandler),
		stopChan:      make(chan struct{}),
		maxWorkers:    maxWorkers,
		taskQueueKey:  "notification:task_queue",
		taskDataKey:   "notification:task_data",
		processingKey: "notification:processing",
		completedKey:  "notification:completed",
	}
}

// RegisterHandler 注册任务处理器
func (q *TaskQueue) RegisterHandler(taskName string, handler TaskHandler) {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.handlers[taskName] = handler
	log.Printf("Registered task handler: %s", taskName)
}

// ScheduleTask 调度任务
func (q *TaskQueue) ScheduleTask(ctx context.Context, task *Task) error {
	// 生成任务ID
	if task.ID == "" {
		task.ID = uuid.New().String()
	}

	task.Status = TaskStatusScheduled
	task.CreatedAt = time.Now()
	task.UpdatedAt = time.Now()

	// 序列化任务
	taskData, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	// 保存任务数据到Hash
	if err := q.redis.HSet(ctx, q.taskDataKey, task.ID, taskData).Err(); err != nil {
		return fmt.Errorf("failed to save task data: %w", err)
	}

	// 添加到有序集合（按执行时间排序）
	score := float64(task.ScheduledAt.Unix())
	if err := q.redis.ZAdd(ctx, q.taskQueueKey, &redis.Z{
		Score:  score,
		Member: task.ID,
	}).Err(); err != nil {
		return fmt.Errorf("failed to add task to queue: %w", err)
	}

	log.Printf("Task scheduled: id=%s, name=%s, scheduled_at=%s",
		task.ID, task.Name, task.ScheduledAt.Format(time.RFC3339))

	return nil
}

// ScheduleDelayedTask 调度延迟任务
func (q *TaskQueue) ScheduleDelayedTask(ctx context.Context, name string, payload map[string]interface{}, delaySeconds int) (*Task, error) {
	task := &Task{
		Type:         TaskTypeDelayed,
		Name:         name,
		Payload:      payload,
		ScheduledAt:  time.Now().Add(time.Duration(delaySeconds) * time.Second),
		DelaySeconds: delaySeconds,
		MaxRetries:   3,
	}

	if err := q.ScheduleTask(ctx, task); err != nil {
		return nil, err
	}

	return task, nil
}

// ScheduleRecurringTask 调度重复任务
func (q *TaskQueue) ScheduleRecurringTask(ctx context.Context, name string, payload map[string]interface{}, intervalSeconds int) (*Task, error) {
	task := &Task{
		Type:        TaskTypeRecurring,
		Name:        name,
		Payload:     payload,
		ScheduledAt: time.Now(),
		Interval:    time.Duration(intervalSeconds) * time.Second,
		MaxRetries:  3,
	}

	if err := q.ScheduleTask(ctx, task); err != nil {
		return nil, err
	}

	return task, nil
}

// Start 启动任务队列处理
func (q *TaskQueue) Start(ctx context.Context) {
	log.Printf("Starting task queue with %d workers...", q.maxWorkers)

	// 启动工作协程
	for i := 0; i < q.maxWorkers; i++ {
		q.wg.Add(1)
		go q.worker(ctx, i)
	}

	log.Println("Task queue started")
}

// Stop 停止任务队列
func (q *TaskQueue) Stop() {
	log.Println("Stopping task queue...")
	close(q.stopChan)
	q.wg.Wait()
	log.Println("Task queue stopped")
}

// worker 工作协程
func (q *TaskQueue) worker(ctx context.Context, workerID int) {
	defer q.wg.Done()

	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	log.Printf("Worker %d started", workerID)

	for {
		select {
		case <-q.stopChan:
			log.Printf("Worker %d stopped", workerID)
			return

		case <-ticker.C:
			// 获取到期任务
			if err := q.processDueTasks(ctx); err != nil {
				log.Printf("Worker %d: error processing tasks: %v", workerID, err)
			}
		}
	}
}

// processDueTasks 处理到期任务
func (q *TaskQueue) processDueTasks(ctx context.Context) error {
	now := time.Now().Unix()

	// 从Sorted Set中获取到期任务
	results, err := q.redis.ZRangeByScoreWithScores(ctx, q.taskQueueKey, &redis.ZRangeBy{
		Min:    "-inf",
		Max:    fmt.Sprintf("%d", now),
		Offset: 0,
		Count:  10, // 每次处理10个任务
	}).Result()
	if err != nil {
		return fmt.Errorf("failed to fetch due tasks: %w", err)
	}

	if len(results) == 0 {
		return nil
	}

	for _, result := range results {
		taskID := result.Member.(string)

		// 获取任务数据
		taskData, err := q.redis.HGet(ctx, q.taskDataKey, taskID).Result()
		if err == redis.Nil {
			// 任务不存在，从队列中移除
			q.redis.ZRem(ctx, q.taskQueueKey, taskID)
			continue
		} else if err != nil {
			log.Printf("Failed to get task data for %s: %v", taskID, err)
			continue
		}

		// 反序列化任务
		var task Task
		if err := json.Unmarshal([]byte(taskData), &task); err != nil {
			log.Printf("Failed to unmarshal task %s: %v", taskID, err)
			continue
		}

		// 检查是否正在处理
		exists, err := q.redis.SIsMember(ctx, q.processingKey, taskID).Result()
		if err != nil || exists {
			continue
		}

		// 标记为处理中
		q.redis.SAdd(ctx, q.processingKey, taskID)

		// 异步执行任务
		go q.executeTask(context.Background(), &task)
	}

	return nil
}

// executeTask 执行任务
func (q *TaskQueue) executeTask(ctx context.Context, task *Task) {
	defer func() {
		// 从处理中集合移除
		q.redis.SRem(ctx, q.processingKey, task.ID)
	}()

	log.Printf("Executing task: id=%s, name=%s", task.ID, task.Name)

	// 更新状态为运行中
	task.Status = TaskStatusRunning
	now := time.Now()
	task.ExecutedAt = &now
	task.UpdatedAt = now
	q.saveTask(ctx, task)

	// 获取处理器
	q.mu.RLock()
	handler, exists := q.handlers[task.Name]
	q.mu.RUnlock()

	if !exists {
		task.Status = TaskStatusFailed
		task.Error = fmt.Sprintf("no handler registered for task: %s", task.Name)
		log.Printf("Task failed: %s", task.Error)
		q.saveTask(ctx, task)
		q.redis.ZRem(ctx, q.taskQueueKey, task.ID)
		return
	}

	// 执行任务
	err := handler(ctx, task)

	completed := time.Now()
	task.CompletedAt = &completed
	task.UpdatedAt = completed

	if err != nil {
		task.RetryCount++
		task.Error = err.Error()

		// 检查是否需要重试
		if task.RetryCount < task.MaxRetries {
			task.Status = TaskStatusScheduled
			// 延迟重试（指数退避）
			retryDelay := time.Duration(1<<uint(task.RetryCount)) * time.Minute
			task.ScheduledAt = time.Now().Add(retryDelay)

			log.Printf("Task failed, will retry (attempt %d/%d): %s",
				task.RetryCount, task.MaxRetries, task.ID)

			// 重新调度
			q.redis.ZAdd(ctx, q.taskQueueKey, &redis.Z{
				Score:  float64(task.ScheduledAt.Unix()),
				Member: task.ID,
			})
		} else {
			task.Status = TaskStatusFailed
			log.Printf("Task failed after %d retries: %s", task.MaxRetries, task.ID)
			q.redis.ZRem(ctx, q.taskQueueKey, task.ID)
		}
	} else {
		task.Status = TaskStatusCompleted
		log.Printf("Task completed: id=%s, name=%s", task.ID, task.Name)

		// 从队列中移除
		q.redis.ZRem(ctx, q.taskQueueKey, task.ID)

		// 如果是重复任务，重新调度下一次
		if task.Type == TaskTypeRecurring && task.Interval > 0 {
			nextTask := &Task{
				Type:        task.Type,
				Name:        task.Name,
				Payload:     task.Payload,
				ScheduledAt: time.Now().Add(task.Interval),
				Interval:    task.Interval,
				MaxRetries:  task.MaxRetries,
			}
			q.ScheduleTask(ctx, nextTask)
		}

		// 记录到已完成列表
		q.redis.LPush(ctx, q.completedKey, task.ID)
		q.redis.LTrim(ctx, q.completedKey, 0, 999) // 只保留最近1000条
	}

	// 保存任务状态
	q.saveTask(ctx, task)
}

// saveTask 保存任务数据
func (q *TaskQueue) saveTask(ctx context.Context, task *Task) error {
	taskData, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	return q.redis.HSet(ctx, q.taskDataKey, task.ID, taskData).Err()
}

// GetTask 获取任务信息
func (q *TaskQueue) GetTask(ctx context.Context, taskID string) (*Task, error) {
	taskData, err := q.redis.HGet(ctx, q.taskDataKey, taskID).Result()
	if err == redis.Nil {
		return nil, fmt.Errorf("task not found: %s", taskID)
	} else if err != nil {
		return nil, fmt.Errorf("failed to get task: %w", err)
	}

	var task Task
	if err := json.Unmarshal([]byte(taskData), &task); err != nil {
		return nil, fmt.Errorf("failed to unmarshal task: %w", err)
	}

	return &task, nil
}

// CancelTask 取消任务
func (q *TaskQueue) CancelTask(ctx context.Context, taskID string) error {
	// 从队列中移除
	if err := q.redis.ZRem(ctx, q.taskQueueKey, taskID).Err(); err != nil {
		return fmt.Errorf("failed to remove task from queue: %w", err)
	}

	// 更新任务状态
	task, err := q.GetTask(ctx, taskID)
	if err != nil {
		return err
	}

	task.Status = TaskStatusCancelled
	task.UpdatedAt = time.Now()

	return q.saveTask(ctx, task)
}

// ListPendingTasks 列出待处理任务
func (q *TaskQueue) ListPendingTasks(ctx context.Context, limit int64) ([]*Task, error) {
	// 获取任务ID列表
	taskIDs, err := q.redis.ZRange(ctx, q.taskQueueKey, 0, limit-1).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to list pending tasks: %w", err)
	}

	tasks := make([]*Task, 0, len(taskIDs))
	for _, taskID := range taskIDs {
		task, err := q.GetTask(ctx, taskID)
		if err != nil {
			log.Printf("Failed to get task %s: %v", taskID, err)
			continue
		}
		tasks = append(tasks, task)
	}

	return tasks, nil
}

// GetStats 获取队列统计信息
func (q *TaskQueue) GetStats(ctx context.Context) (map[string]interface{}, error) {
	pendingCount, err := q.redis.ZCard(ctx, q.taskQueueKey).Result()
	if err != nil {
		return nil, err
	}

	processingCount, err := q.redis.SCard(ctx, q.processingKey).Result()
	if err != nil {
		return nil, err
	}

	completedCount, err := q.redis.LLen(ctx, q.completedKey).Result()
	if err != nil {
		return nil, err
	}

	totalTasks, err := q.redis.HLen(ctx, q.taskDataKey).Result()
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"pending_tasks":    pendingCount,
		"processing_tasks": processingCount,
		"completed_tasks":  completedCount,
		"total_tasks":      totalTasks,
		"workers":          q.maxWorkers,
	}, nil
}
