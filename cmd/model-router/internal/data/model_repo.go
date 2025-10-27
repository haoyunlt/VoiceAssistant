package data

import (
	"context"
	"encoding/json"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/lib/pq"
	"gorm.io/gorm"
)

// ModelPO 模型持久化对象
type ModelPO struct {
	ID              string         `gorm:"primaryKey;size:64"`
	Name            string         `gorm:"size:100;not null;uniqueIndex:idx_name"`
	DisplayName     string         `gorm:"size:255;not null"`
	Provider        string         `gorm:"size:50;not null;index:idx_provider"`
	Type            string         `gorm:"size:20;not null;index:idx_type"`
	Status          string         `gorm:"size:20;not null;index:idx_status"`
	Endpoint        string         `gorm:"size:500;not null"`
	APIKey          string         `gorm:"size:500"`
	MaxTokens       int            `gorm:"not null"`
	ContextWindow   int            `gorm:"not null"`
	InputPricePerK  float64        `gorm:"type:decimal(10,6);not null"`
	OutputPricePerK float64        `gorm:"type:decimal(10,6);not null"`
	Priority        int            `gorm:"not null;index:idx_priority"`
	Weight          int            `gorm:"not null"`
	Timeout         int            `gorm:"not null"`
	RetryCount      int            `gorm:"not null"`
	RateLimit       int            `gorm:"not null"`
	Capabilities    pq.StringArray `gorm:"type:text[]"`
	Metadata        string         `gorm:"type:jsonb"`
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// TableName 表名
func (ModelPO) TableName() string {
	return "model_router.models"
}

// ModelRepository 模型仓储实现
type ModelRepository struct {
	data *Data
	log  *log.Helper
}

// NewModelRepo 创建模型仓储
func NewModelRepo(data *Data, logger log.Logger) domain.ModelRepository {
	return &ModelRepository{
		data: data,
		log:  log.NewHelper(logger),
	}
}

// Create 创建模型
func (r *ModelRepository) Create(ctx context.Context, model *domain.Model) error {
	po, err := r.toModelPO(model)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		r.log.Errorf("failed to create model: %v", err)
		return err
	}

	return nil
}

// GetByID 根据ID获取模型
func (r *ModelRepository) GetByID(ctx context.Context, id string) (*domain.Model, error) {
	var po ModelPO
	if err := r.data.db.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrModelNotFound
		}
		r.log.Errorf("failed to get model: %v", err)
		return nil, err
	}

	return r.toDomainModel(&po)
}

// GetByName 根据名称获取模型
func (r *ModelRepository) GetByName(ctx context.Context, name string) (*domain.Model, error) {
	var po ModelPO
	if err := r.data.db.WithContext(ctx).Where("name = ?", name).First(&po).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrModelNotFound
		}
		r.log.Errorf("failed to get model by name: %v", err)
		return nil, err
	}

	return r.toDomainModel(&po)
}

// Update 更新模型
func (r *ModelRepository) Update(ctx context.Context, model *domain.Model) error {
	po, err := r.toModelPO(model)
	if err != nil {
		return err
	}

	if err := r.data.db.WithContext(ctx).
		Model(&ModelPO{}).
		Where("id = ?", model.ID).
		Updates(po).Error; err != nil {
		r.log.Errorf("failed to update model: %v", err)
		return err
	}

	return nil
}

// Delete 删除模型
func (r *ModelRepository) Delete(ctx context.Context, id string) error {
	if err := r.data.db.WithContext(ctx).Delete(&ModelPO{}, "id = ?", id).Error; err != nil {
		r.log.Errorf("failed to delete model: %v", err)
		return err
	}

	return nil
}

// ListByProvider 根据提供商获取模型列表
func (r *ModelRepository) ListByProvider(ctx context.Context, provider domain.ModelProvider) ([]*domain.Model, error) {
	var pos []ModelPO

	if err := r.data.db.WithContext(ctx).
		Where("provider = ?", provider).
		Order("priority DESC").
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list models by provider: %v", err)
		return nil, err
	}

	return r.toDomainModels(pos)
}

// ListByType 根据类型获取模型列表
func (r *ModelRepository) ListByType(ctx context.Context, modelType domain.ModelType) ([]*domain.Model, error) {
	var pos []ModelPO

	if err := r.data.db.WithContext(ctx).
		Where("type = ?", modelType).
		Order("priority DESC").
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list models by type: %v", err)
		return nil, err
	}

	return r.toDomainModels(pos)
}

// ListAvailable 获取可用模型列表
func (r *ModelRepository) ListAvailable(ctx context.Context, modelType domain.ModelType) ([]*domain.Model, error) {
	var pos []ModelPO

	if err := r.data.db.WithContext(ctx).
		Where("type = ? AND status = ?", modelType, domain.ModelStatusActive).
		Order("priority DESC").
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list available models: %v", err)
		return nil, err
	}

	return r.toDomainModels(pos)
}

// ListAll 获取所有模型
func (r *ModelRepository) ListAll(ctx context.Context, offset, limit int) ([]*domain.Model, int64, error) {
	var pos []ModelPO
	var total int64

	// 查询总数
	if err := r.data.db.WithContext(ctx).
		Model(&ModelPO{}).
		Count(&total).Error; err != nil {
		r.log.Errorf("failed to count models: %v", err)
		return nil, 0, err
	}

	// 查询列表
	if err := r.data.db.WithContext(ctx).
		Order("created_at DESC").
		Offset(offset).
		Limit(limit).
		Find(&pos).Error; err != nil {
		r.log.Errorf("failed to list models: %v", err)
		return nil, 0, err
	}

	models, err := r.toDomainModels(pos)
	if err != nil {
		return nil, 0, err
	}

	return models, total, nil
}

// toModelPO 转换为持久化对象
func (r *ModelRepository) toModelPO(model *domain.Model) (*ModelPO, error) {
	metadataJSON, _ := json.Marshal(model.Metadata)

	return &ModelPO{
		ID:              model.ID,
		Name:            model.Name,
		DisplayName:     model.DisplayName,
		Provider:        string(model.Provider),
		Type:            string(model.Type),
		Status:          string(model.Status),
		Endpoint:        model.Endpoint,
		APIKey:          model.APIKey,
		MaxTokens:       model.MaxTokens,
		ContextWindow:   model.ContextWindow,
		InputPricePerK:  model.InputPricePerK,
		OutputPricePerK: model.OutputPricePerK,
		Priority:        model.Priority,
		Weight:          model.Weight,
		Timeout:         model.Timeout,
		RetryCount:      model.RetryCount,
		RateLimit:       model.RateLimit,
		Capabilities:    pq.StringArray(model.Capabilities),
		Metadata:        string(metadataJSON),
		CreatedAt:       model.CreatedAt,
		UpdatedAt:       model.UpdatedAt,
	}, nil
}

// toDomainModel 转换为领域对象
func (r *ModelRepository) toDomainModel(po *ModelPO) (*domain.Model, error) {
	var metadata map[string]interface{}
	if po.Metadata != "" {
		json.Unmarshal([]byte(po.Metadata), &metadata)
	}

	return &domain.Model{
		ID:              po.ID,
		Name:            po.Name,
		DisplayName:     po.DisplayName,
		Provider:        domain.ModelProvider(po.Provider),
		Type:            domain.ModelType(po.Type),
		Status:          domain.ModelStatus(po.Status),
		Endpoint:        po.Endpoint,
		APIKey:          po.APIKey,
		MaxTokens:       po.MaxTokens,
		ContextWindow:   po.ContextWindow,
		InputPricePerK:  po.InputPricePerK,
		OutputPricePerK: po.OutputPricePerK,
		Priority:        po.Priority,
		Weight:          po.Weight,
		Timeout:         po.Timeout,
		RetryCount:      po.RetryCount,
		RateLimit:       po.RateLimit,
		Capabilities:    []string(po.Capabilities),
		Metadata:        metadata,
		CreatedAt:       po.CreatedAt,
		UpdatedAt:       po.UpdatedAt,
	}, nil
}

// toDomainModels 批量转换
func (r *ModelRepository) toDomainModels(pos []ModelPO) ([]*domain.Model, error) {
	models := make([]*domain.Model, 0, len(pos))
	for _, po := range pos {
		model, err := r.toDomainModel(&po)
		if err != nil {
			r.log.Warnf("failed to convert model: %v", err)
			continue
		}
		models = append(models, model)
	}
	return models, nil
}
