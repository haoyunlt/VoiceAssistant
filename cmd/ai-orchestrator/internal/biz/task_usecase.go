package biz

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// TaskUsecase 任务用例
type TaskUsecase struct {
	repo      domain.TaskRepository
	pipelines map[domain.TaskType]domain.Pipeline
	log       *log.Helper
}

// NewTaskUsecase 创建任务用例
func NewTaskUsecase(
	repo domain.TaskRepository,
	ragPipeline *domain.RAGPipeline,
	agentPipeline *domain.AgentPipeline,
	voicePipeline *domain.VoicePipeline,
	logger log.Logger,
) *TaskUsecase {
	pipelines := map[domain.TaskType]domain.Pipeline{
		domain.TaskTypeRAG:   ragPipeline,
		domain.TaskTypeAgent: agentPipeline,
		domain.TaskTypeVoice: voicePipeline,
	}

	return &TaskUsecase{
		repo:      repo,
		pipelines: pipelines,
		log:       log.NewHelper(logger),
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
		uc.log.WithContext(ctx).Errorf("task %s failed: %v", task.ID, err)
		return nil, err
	}

	// 完成任务
	task.Complete(output)
	if err := uc.repo.Update(ctx, task); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update task completion: %v", err)
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

// GetTask 获取任务详情
func (uc *TaskUsecase) GetTask(ctx context.Context, taskID string) (*domain.Task, error) {
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

// ProcessPendingTasks 处理待执行任务（后台任务）
func (uc *TaskUsecase) ProcessPendingTasks(ctx context.Context) error {
	tasks, err := uc.repo.ListPending(ctx, 10)
	if err != nil {
		return err
	}

	for _, task := range tasks {
		// 使用goroutine异步执行
		go func(t *domain.Task) {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
			defer cancel()

			_, err := uc.ExecuteTask(ctx, t.ID)
			if err != nil {
				uc.log.Errorf("background task %s execution failed: %v", t.ID, err)
			}
		}(task)
	}

	return nil
}
