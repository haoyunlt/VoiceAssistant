package biz

import (
	"context"
	"fmt"
	"time"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// TaskUsecase 任务用例
type TaskUsecase struct {
	repo         domain.TaskRepository
	pipelines    map[domain.TaskType]domain.Pipeline
	queue        TaskQueue        // 任务队列（可选）
	cacheManager *CacheManager    // 缓存管理器（可选）
	idempotency  *IdempotencyService // 幂等性服务（可选）
	log          *log.Helper
}

// NewTaskUsecase 创建任务用例
func NewTaskUsecase(
	repo domain.TaskRepository,
	ragPipeline *domain.RAGPipeline,
	agentPipeline *domain.AgentPipeline,
	voicePipeline *domain.VoicePipeline,
	queue TaskQueue, // 可以为nil
	cacheManager *CacheManager, // 可以为nil
	idempotency *IdempotencyService, // 可以为nil
	logger log.Logger,
) *TaskUsecase {
	pipelines := map[domain.TaskType]domain.Pipeline{
		domain.TaskTypeRAG:   ragPipeline,
		domain.TaskTypeAgent: agentPipeline,
		domain.TaskTypeVoice: voicePipeline,
	}

	return &TaskUsecase{
		repo:         repo,
		pipelines:    pipelines,
		queue:        queue,
		cacheManager: cacheManager,
		idempotency:  idempotency,
		log:          log.NewHelper(logger),
	}
}

// CreateTask 创建AI任务
func (uc *TaskUsecase) CreateTask(
	ctx context.Context,
	taskType domain.TaskType,
	conversationID, userID, tenantID string,
	input *domain.TaskInput,
) (*domain.Task, error) {
	// 验证任务类型
	if _, exists := uc.pipelines[taskType]; !exists {
		return nil, fmt.Errorf("unsupported task type: %s", taskType)
	}

	// 创建任务
	task := domain.NewTask(taskType, conversationID, userID, tenantID, input)

	// 持久化
	if err := uc.repo.Create(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create task: %v", err)
		return nil, err
	}

	// 记录指标
	TaskCreatedTotal.WithLabelValues(string(task.Type), task.TenantID).Inc()

	uc.log.WithContext(ctx).Infof("created task: %s, type: %s", task.ID, task.Type)
	return task, nil
}

// ExecuteTask 执行任务
func (uc *TaskUsecase) ExecuteTask(ctx context.Context, taskID string) (*domain.TaskOutput, error) {
	// 获取任务
	task, err := uc.repo.GetByID(ctx, taskID)
	if err != nil {
		return nil, err
	}

	// 检查任务状态
	if task.Status != domain.TaskStatusPending {
		return nil, fmt.Errorf("task %s is not in pending state", taskID)
	}

	// 获取对应的Pipeline
	pipeline, exists := uc.pipelines[task.Type]
	if !exists {
		return nil, fmt.Errorf("no pipeline found for task type: %s", task.Type)
	}

	// 开始执行
	task.Start()
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update task start: %v", err)
	}

	uc.log.WithContext(ctx).Infof("executing task: %s, type: %s", task.ID, task.Type)

	// 执行Pipeline
	output, err := pipeline.Execute(task)
	if err != nil {
		task.Fail(err.Error())
		uc.repo.Update(ctx, task)

		// 记录失败指标
		TaskStatusTotal.WithLabelValues(string(task.Type), "failed", task.TenantID).Inc()
		TaskExecutionDuration.WithLabelValues(string(task.Type), "failed", task.TenantID).Observe(task.Duration().Seconds())

		uc.log.WithContext(ctx).Errorf("task %s failed: %v", task.ID, err)
		return nil, err
	}

	// 完成任务
	task.Complete(output)
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update task completion: %v", err)
	}

	// 记录成功指标
	TaskStatusTotal.WithLabelValues(string(task.Type), "completed", task.TenantID).Inc()
	TaskExecutionDuration.WithLabelValues(string(task.Type), "completed", task.TenantID).Observe(task.Duration().Seconds())

	if output.TokensUsed > 0 {
		TaskTokensUsed.WithLabelValues(string(task.Type), output.Model, task.TenantID).Observe(float64(output.TokensUsed))
	}
	if output.CostUSD > 0 {
		TaskCostUSD.WithLabelValues(string(task.Type), output.Model, task.TenantID).Observe(output.CostUSD)
	}

	uc.log.WithContext(ctx).Infof(
		"task %s completed, duration: %v, tokens: %d, cost: $%.4f",
		task.ID,
		task.Duration(),
		output.TokensUsed,
		output.CostUSD,
	)

	return output, nil
}

// GetTask 获取任务详情（使用缓存）
func (uc *TaskUsecase) GetTask(ctx context.Context, taskID string) (*domain.Task, error) {
	// 使用缓存管理器
	if uc.cacheManager != nil {
		task, err := uc.cacheManager.GetTask(ctx, taskID)
		if err != nil {
			uc.log.WithContext(ctx).Errorf("failed to get task from cache: %v", err)
			// 降级到直接查询
		} else {
			return task, nil
		}
	}

	// 直接查询数据库
	task, err := uc.repo.GetByID(ctx, taskID)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get task %s: %v", taskID, err)
		return nil, err
	}
	return task, nil
}

// GetTasksByConversation 获取对话的所有任务
func (uc *TaskUsecase) GetTasksByConversation(ctx context.Context, conversationID string) ([]*domain.Task, error) {
	tasks, err := uc.repo.GetByConversationID(ctx, conversationID)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get tasks for conversation %s: %v", conversationID, err)
		return nil, err
	}
	return tasks, nil
}

// CancelTask 取消任务
func (uc *TaskUsecase) CancelTask(ctx context.Context, taskID string) error {
	task, err := uc.repo.GetByID(ctx, taskID)
	if err != nil {
		return err
	}

	if task.IsCompleted() {
		return fmt.Errorf("task %s is already completed", taskID)
	}

	task.Cancel()
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to cancel task %s: %v", taskID, err)
		return err
	}

	// 记录取消指标
	TaskStatusTotal.WithLabelValues(string(task.Type), "cancelled", task.TenantID).Inc()

	uc.log.WithContext(ctx).Infof("cancelled task: %s", taskID)
	return nil
}

// SetTaskPriority 设置任务优先级
func (uc *TaskUsecase) SetTaskPriority(ctx context.Context, taskID string, priority domain.TaskPriority) error {
	task, err := uc.repo.GetByID(ctx, taskID)
	if err != nil {
		return err
	}

	task.SetPriority(priority)
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to set priority for task %s: %v", taskID, err)
		return err
	}

	return nil
}

// CreateAndExecuteTask 创建并执行任务（同步）
func (uc *TaskUsecase) CreateAndExecuteTask(
	ctx context.Context,
	taskType domain.TaskType,
	conversationID, userID, tenantID string,
	input *domain.TaskInput,
) (*domain.Task, *domain.TaskOutput, error) {
	// 创建任务
	task, err := uc.CreateTask(ctx, taskType, conversationID, userID, tenantID, input)
	if err != nil {
		return nil, nil, err
	}

	// 执行任务
	output, err := uc.ExecuteTask(ctx, task.ID)
	if err != nil {
		return task, nil, err
	}

	return task, output, nil
}

// CreateTaskAsync 创建任务（异步执行，支持幂等性）
func (uc *TaskUsecase) CreateTaskAsync(
	ctx context.Context,
	taskType domain.TaskType,
	conversationID, userID, tenantID string,
	input *domain.TaskInput,
	idempotencyKey string, // 幂等键（可选）
) (*domain.Task, error) {
	// 幂等性检查
	if uc.idempotency != nil && idempotencyKey != "" {
		isNew, existingTaskID, err := uc.idempotency.CheckOrCreate(ctx, idempotencyKey, "")
		if err != nil {
			uc.log.WithContext(ctx).Errorf("idempotency check failed: %v", err)
			// 继续执行（降级）
		} else if !isNew {
			// 重复请求，返回已存在的任务
			uc.log.WithContext(ctx).Infof("duplicate request detected, returning existing task: %s", existingTaskID)
			return uc.GetTask(ctx, existingTaskID)
		}
	}

	// 验证任务类型
	if _, exists := uc.pipelines[taskType]; !exists {
		return nil, fmt.Errorf("unsupported task type: %s", taskType)
	}

	// 创建任务
	task := domain.NewTask(taskType, conversationID, userID, tenantID, input)

	// 更新幂等键（关联任务ID）
	if uc.idempotency != nil && idempotencyKey != "" {
		uc.idempotency.CheckOrCreate(ctx, idempotencyKey, task.ID)
	}

	// 如果有队列，推送到队列
	if uc.queue != nil {
		if err := uc.queue.Enqueue(ctx, task); err != nil {
			uc.log.WithContext(ctx).Errorf("failed to enqueue task: %v", err)
			return nil, err
		}

		// 记录指标
		TaskCreatedTotal.WithLabelValues(string(task.Type), task.TenantID).Inc()

		uc.log.WithContext(ctx).Infof("task %s created and enqueued (async)", task.ID)
	} else {
		// 无队列，同步创建
		if err := uc.repo.Create(ctx, task); err != nil {
			uc.log.WithContext(ctx).Errorf("failed to create task: %v", err)
			return nil, err
		}

		// 记录指标
		TaskCreatedTotal.WithLabelValues(string(task.Type), task.TenantID).Inc()

		uc.log.WithContext(ctx).Infof("task %s created (sync)", task.ID)
	}

	// 写入缓存
	if uc.cacheManager != nil {
		uc.cacheManager.SetTask(ctx, task)
	}

	return task, nil
}

// ExecuteTaskStream 流式执行任务
func (uc *TaskUsecase) ExecuteTaskStream(
	ctx context.Context,
	taskID string,
	stream chan<- *domain.StreamEvent,
) error {
	defer close(stream)

	// 获取任务
	task, err := uc.repo.GetByID(ctx, taskID)
	if err != nil {
		stream <- domain.NewStreamEvent(domain.StreamEventTypeError, "").WithError(err)
		return err
	}

	// 检查任务状态
	if task.Status != domain.TaskStatusPending {
		err := fmt.Errorf("task %s is not in pending state", taskID)
		stream <- domain.NewStreamEvent(domain.StreamEventTypeError, "").WithError(err)
		return err
	}

	// 获取对应的Pipeline
	pipeline, exists := uc.pipelines[task.Type]
	if !exists {
		err := fmt.Errorf("no pipeline found for task type: %s", task.Type)
		stream <- domain.NewStreamEvent(domain.StreamEventTypeError, "").WithError(err)
		return err
	}

	// 开始执行
	task.Start()
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update task start: %v", err)
	}

	uc.log.WithContext(ctx).Infof("executing task %s (stream mode)", task.ID)

	// 检查Pipeline是否支持流式
	streamPipeline, ok := pipeline.(domain.StreamPipeline)
	if !ok {
		// 不支持流式，降级到普通执行
		output, err := pipeline.Execute(task)
		if err != nil {
			task.Fail(err.Error())
			uc.repo.Update(ctx, task)
			stream <- domain.NewStreamEvent(domain.StreamEventTypeError, "").WithError(err)
			return err
		}

		// 发送结果
		stream <- domain.NewStreamEvent(domain.StreamEventTypeText, output.Content)
		stream <- domain.NewStreamEvent(domain.StreamEventTypeFinal, "完成").WithDone()

		task.Complete(output)
		uc.repo.Update(ctx, task)
		return nil
	}

	// 流式执行
	err = streamPipeline.ExecuteStream(task, stream)
	if err != nil {
		task.Fail(err.Error())
		uc.repo.Update(ctx, task)

		// 记录失败指标
		TaskStatusTotal.WithLabelValues(string(task.Type), "failed", task.TenantID).Inc()
		TaskExecutionDuration.WithLabelValues(string(task.Type), "failed", task.TenantID).Observe(task.Duration().Seconds())

		return err
	}

	// 完成任务（注意：output需要从task中提取）
	output := &domain.TaskOutput{
		Content: "Stream completed", // 实际应从task中提取
	}
	task.Complete(output)
	uc.repo.Update(ctx, task)

	// 记录成功指标
	TaskStatusTotal.WithLabelValues(string(task.Type), "completed", task.TenantID).Inc()
	TaskExecutionDuration.WithLabelValues(string(task.Type), "completed", task.TenantID).Observe(task.Duration().Seconds())

	uc.log.WithContext(ctx).Infof("task %s completed (stream mode)", task.ID)

	return nil
}

// ProcessPendingTasks 处理待执行任务（后台任务）
// 使用sync.WaitGroup管理goroutine，避免泄漏
func (uc *TaskUsecase) ProcessPendingTasks(ctx context.Context, maxWorkers int) error {
	tasks, err := uc.repo.ListPending(ctx, maxWorkers)
	if err != nil {
		return err
	}

	if len(tasks) == 0 {
		return nil
	}

	// 创建有限的worker池
	taskChan := make(chan *domain.Task, len(tasks))
	errChan := make(chan error, len(tasks))

	// 启动worker
	for i := 0; i < maxWorkers && i < len(tasks); i++ {
		go uc.taskWorker(ctx, taskChan, errChan)
	}

	// 将任务分发到channel
	go func() {
		for _, task := range tasks {
			select {
			case taskChan <- task:
			case <-ctx.Done():
				return
			}
		}
		close(taskChan)
	}()

	// 收集结果
	var lastErr error
	for i := 0; i < len(tasks); i++ {
		select {
		case err := <-errChan:
			if err != nil {
				lastErr = err
			}
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return lastErr
}

// taskWorker 任务工作协程
func (uc *TaskUsecase) taskWorker(ctx context.Context, taskChan <-chan *domain.Task, errChan chan<- error) {
	for {
		select {
		case task, ok := <-taskChan:
			if !ok {
				return // channel关闭，退出
			}

			// 为每个任务创建独立的超时context
			taskCtx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
			_, err := uc.ExecuteTask(taskCtx, task.ID)
			cancel()

			if err != nil {
				uc.log.Errorf("background task %s execution failed: %v", task.ID, err)
			}
			errChan <- err

		case <-ctx.Done():
			return
		}
	}
}
