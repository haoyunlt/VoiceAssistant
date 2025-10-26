package domain

import (
	"context"
)

// ModelRepository 模型仓储接口
type ModelRepository interface {
	// Create 创建模型
	Create(ctx context.Context, model *Model) error

	// GetByID 根据ID获取模型
	GetByID(ctx context.Context, id string) (*Model, error)

	// GetByName 根据名称获取模型
	GetByName(ctx context.Context, name string) (*Model, error)

	// Update 更新模型
	Update(ctx context.Context, model *Model) error

	// Delete 删除模型
	Delete(ctx context.Context, id string) error

	// ListByProvider 根据提供商获取模型列表
	ListByProvider(ctx context.Context, provider ModelProvider) ([]*Model, error)

	// ListByType 根据类型获取模型列表
	ListByType(ctx context.Context, modelType ModelType) ([]*Model, error)

	// ListAvailable 获取可用模型列表
	ListAvailable(ctx context.Context, modelType ModelType) ([]*Model, error)

	// ListAll 获取所有模型
	ListAll(ctx context.Context, offset, limit int) ([]*Model, int64, error)
}

// ModelMetricsRepository 模型指标仓储接口
type ModelMetricsRepository interface {
	// Save 保存指标
	Save(ctx context.Context, metrics *ModelMetrics) error

	// GetByModelID 根据模型ID获取指标
	GetByModelID(ctx context.Context, modelID string) (*ModelMetrics, error)

	// ListAll 获取所有指标
	ListAll(ctx context.Context) ([]*ModelMetrics, error)

	// UpdateMetrics 更新指标
	UpdateMetrics(ctx context.Context, modelID string, success bool, latencyMs int, tokens int, cost float64) error
}
