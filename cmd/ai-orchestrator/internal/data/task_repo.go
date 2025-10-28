package data

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/ai-orchestrator/internal/domain"
	"gorm.io/gorm"
)

// TaskPO 任务持久化对象
type TaskPO struct {
	ID             string `gorm:"primaryKey;size:64"`
	Type           string `gorm:"size:20;not null;index:idx_type"`
	Status         string `gorm:"size:20;not null;index:idx_status"`
	Priority       int    `gorm:"not null;index:idx_priority"`
	ConversationID string `gorm:"size:64;not null;index:idx_conversation"`
	UserID         string `gorm:"size:64;not null;index:idx_user"`
	TenantID       string `gorm:"size:64;not null;index:idx_tenant"`
	Input          string `gorm:"type:jsonb"`
	Output         string `gorm:"type:jsonb"`
	Steps          string `gorm:"type:jsonb"`
	Metadata       string `gorm:"type:jsonb"`
	CreatedAt      time.Time
	UpdatedAt      time.Time
	StartedAt      *time.Time
	CompletedAt    *time.Time
}

// TableName 表名
func (TaskPO) TableName() string {
	return "ai_orchestrator.tasks"
}

// TaskRepository 任务仓储实现
type TaskRepository struct {
	data *Data
	log  *log.Helper
}

// NewTaskRepo 创建任务仓储
func NewTaskRepo(data *Data, logger log.Logger) domain.TaskRepository {
	return &TaskRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create 创建任务
func (r *TaskRepository) Create(ctx context.Context, task *domain.Task) error {
	po, err := r.toTaskPO(task)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create task: %v", err)
		return err
	}

	return nil
}

// GetByID 根据ID获取任务
func (r *TaskRepository) GetByID(ctx context.Context, id string) (*domain.Task, error) {
	var po TaskPO
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, fmt.Errorf("task not found: %s", id)
		}
		r.log.Errorf("failed to get task: %v", err)
		return nil, err
	}

	return r.toDomainTask(&po)
}

// GetByConversationID 获取对话的任务列表
func (r *TaskRepository) GetByConversationID(ctx context.Context, conversationID string) ([]*domain.Task, error) {
	var pos []TaskPO
	if err := r.data.db.WithContext(ctx).
		Where("conversation_id = ?", conversationID).
		Order("created_at DESC").
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to get tasks by conversation: %v", err)
		return nil, err
	}

	tasks := make([]*domain.Task, 0, len(pos))
	for _, po := range pos {
		task, err := r.toDomainTask(&po)
		if err != nil {
			r.log.Warnf("failed to convert task: %v", err)
			continue
		}
		tasks = append(tasks, task)
	}

	return tasks, nil
}

// Update 更新任务
func (r *TaskRepository) Update(ctx context.Context, task *domain.Task) error {
	po, err := r.toTaskPO(task)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).
		Model(&TaskPO{}).
		Where("id = ?", task.ID).
		Updates(po).Error; err != nil {
		r.log.Errorf("failed to update task: %v", err)
		return err
	}

	return nil
}

// ListPending 获取待执行任务列表
func (r *TaskRepository) ListPending(ctx context.Context, limit int) ([]*domain.Task, error) {
	var pos []TaskPO
	if err := r.data.db.WithContext(ctx).
		Where("status = ?", domain.TaskStatusPending).
		Order("priority DESC, created_at ASC").
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list pending tasks: %v", err)
		return nil, err
	}

	tasks := make([]*domain.Task, 0, len(pos))
	for _, po := range pos {
		task, err := r.toDomainTask(&po)
		if err != nil {
			r.log.Warnf("failed to convert task: %v", err)
			continue
		}
		tasks = append(tasks, task)
	}

	return tasks, nil
}

// toTaskPO 转换为持久化对象
func (r *TaskRepository) toTaskPO(task *domain.Task) (*TaskPO, error) {
	inputJSON, err := json.Marshal(task.Input)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal task input: %w", err)
	}

	outputJSON, err := json.Marshal(task.Output)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal task output: %w", err)
	}

	stepsJSON, err := json.Marshal(task.Steps)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal task steps: %w", err)
	}

	metadataJSON, err := json.Marshal(task.Metadata)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal task metadata: %w", err)
	}

	return &TaskPO{
		ID:             task.ID,
		Type:           string(task.Type),
		Status:         string(task.Status),
		Priority:       int(task.Priority),
		ConversationID: task.ConversationID,
		UserID:         task.UserID,
		TenantID:       task.TenantID,
		Input:          string(inputJSON),
		Output:         string(outputJSON),
		Steps:          string(stepsJSON),
		Metadata:       string(metadataJSON),
		CreatedAt:      task.CreatedAt,
		UpdatedAt:      task.UpdatedAt,
		StartedAt:      task.StartedAt,
		CompletedAt:    task.CompletedAt,
	}, nil
}

// toDomainTask 转换为领域对象
func (r *TaskRepository) toDomainTask(po *TaskPO) (*domain.Task, error) {
	var input domain.TaskInput
	var output *domain.TaskOutput
	var steps []*domain.TaskStep
	var metadata map[string]interface{}

	if po.Input != "" {
		if err := json.Unmarshal([]byte(po.Input), &input); err != nil {
			r.log.Warnf("failed to unmarshal task input: %v", err)
			// 继续处理，使用空的input
		}
	}
	if po.Output != "" {
		if err := json.Unmarshal([]byte(po.Output), &output); err != nil {
			r.log.Warnf("failed to unmarshal task output: %v", err)
			// 继续处理，output保持为nil
		}
	}
	if po.Steps != "" {
		if err := json.Unmarshal([]byte(po.Steps), &steps); err != nil {
			r.log.Warnf("failed to unmarshal task steps: %v", err)
			steps = make([]*domain.TaskStep, 0)
		}
	}
	if po.Metadata != "" {
		if err := json.Unmarshal([]byte(po.Metadata), &metadata); err != nil {
			r.log.Warnf("failed to unmarshal task metadata: %v", err)
			metadata = make(map[string]interface{})
		}
	}

	// 如果metadata为nil，初始化为空map
	if metadata == nil {
		metadata = make(map[string]interface{})
	}
	// 如果steps为nil，初始化为空切片
	if steps == nil {
		steps = make([]*domain.TaskStep, 0)
	}

	return &domain.Task{
		ID:             po.ID,
		Type:           domain.TaskType(po.Type),
		Status:         domain.TaskStatus(po.Status),
		Priority:       domain.TaskPriority(po.Priority),
		ConversationID: po.ConversationID,
		UserID:         po.UserID,
		TenantID:       po.TenantID,
		Input:          &input,
		Output:         output,
		Steps:          steps,
		Metadata:       metadata,
		CreatedAt:      po.CreatedAt,
		UpdatedAt:      po.UpdatedAt,
		StartedAt:      po.StartedAt,
		CompletedAt:    po.CompletedAt,
	}, nil
}
