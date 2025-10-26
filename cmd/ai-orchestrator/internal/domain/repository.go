package domain

import (
	"context"
)

// TaskRepository 任务仓储接口
type TaskRepository interface {
	// Create 创建任务
	Create(ctx context.Context, task *Task) error

	// GetByID 根据ID获取任务
	GetByID(ctx context.Context, id string) (*Task, error)

	// GetByConversationID 获取对话的任务列表
	GetByConversationID(ctx context.Context, conversationID string) ([]*Task, error)

	// Update 更新任务
	Update(ctx context.Context, task *Task) error

	// ListPending 获取待执行任务列表
	ListPending(ctx context.Context, limit int) ([]*Task, error)
}
