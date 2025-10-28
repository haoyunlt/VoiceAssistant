package biz

import (
	"context"

	"voicehelper/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ModelUsecase 模型用例
type ModelUsecase struct {
	modelRepo   domain.ModelRepository
	metricsRepo domain.ModelMetricsRepository
	log         *log.Helper
}

// NewModelUsecase 创建模型用例
func NewModelUsecase(
	modelRepo domain.ModelRepository,
	metricsRepo domain.ModelMetricsRepository,
	logger log.Logger,
) *ModelUsecase {
	return &ModelUsecase{
		modelRepo:   modelRepo,
		metricsRepo: metricsRepo,
		log:         log.NewHelper(logger),
	}
}

// CreateModel 创建模型
func (uc *ModelUsecase) CreateModel(
	ctx context.Context,
	name, displayName string,
	provider domain.ModelProvider,
	modelType domain.ModelType,
	endpoint, apiKey string,
) (*domain.Model, error) {
	// 创建模型
	model := domain.NewModel(
		name,
		displayName,
		provider,
		modelType,
		endpoint,
		apiKey,
	)

	// 验证
	if err := model.Validate(); err != nil {
		uc.log.WithContext(ctx).Errorf("invalid model: %v", err)
		return nil, err
	}

	// 持久化
	if err := uc.modelRepo.Create(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create model: %v", err)
		return nil, err
	}

	// 初始化指标
	metrics := domain.NewModelMetrics(model.ID)
	if err := uc.metricsRepo.Save(ctx, metrics); err != nil {
		uc.log.WithContext(ctx).Warnf("failed to create metrics: %v", err)
	}

	uc.log.WithContext(ctx).Infof("created model: %s, name: %s", model.ID, model.Name)
	return model, nil
}

// GetModel 获取模型
func (uc *ModelUsecase) GetModel(ctx context.Context, id string) (*domain.Model, error) {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get model %s: %v", id, err)
		return nil, err
	}
	return model, nil
}

// GetModelByName 根据名称获取模型
func (uc *ModelUsecase) GetModelByName(ctx context.Context, name string) (*domain.Model, error) {
	model, err := uc.modelRepo.GetByName(ctx, name)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get model by name %s: %v", name, err)
		return nil, err
	}
	return model, nil
}

// UpdateModel 更新模型
func (uc *ModelUsecase) UpdateModel(
	ctx context.Context,
	id, displayName, endpoint string,
) (*domain.Model, error) {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}

	model.Update(displayName, endpoint)

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update model: %v", err)
		return nil, err
	}

	uc.log.WithContext(ctx).Infof("updated model: %s", model.ID)
	return model, nil
}

// DeleteModel 删除模型
func (uc *ModelUsecase) DeleteModel(ctx context.Context, id string) error {
	if err := uc.modelRepo.Delete(ctx, id); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to delete model: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("deleted model: %s", id)
	return nil
}

// ListModels 列出所有模型
func (uc *ModelUsecase) ListModels(
	ctx context.Context,
	offset, limit int,
) ([]*domain.Model, int64, error) {
	models, total, err := uc.modelRepo.ListAll(ctx, offset, limit)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list models: %v", err)
		return nil, 0, err
	}
	return models, total, nil
}

// ListModelsByProvider 根据提供商列出模型
func (uc *ModelUsecase) ListModelsByProvider(
	ctx context.Context,
	provider domain.ModelProvider,
) ([]*domain.Model, error) {
	models, err := uc.modelRepo.ListByProvider(ctx, provider)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list models by provider: %v", err)
		return nil, err
	}
	return models, nil
}

// ListModelsByType 根据类型列出模型
func (uc *ModelUsecase) ListModelsByType(
	ctx context.Context,
	modelType domain.ModelType,
) ([]*domain.Model, error) {
	models, err := uc.modelRepo.ListByType(ctx, modelType)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list models by type: %v", err)
		return nil, err
	}
	return models, nil
}

// ActivateModel 激活模型
func (uc *ModelUsecase) ActivateModel(ctx context.Context, id string) error {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	model.Activate()

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to activate model: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("activated model: %s", model.ID)
	return nil
}

// DeactivateModel 停用模型
func (uc *ModelUsecase) DeactivateModel(ctx context.Context, id string) error {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	model.Deactivate()

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to deactivate model: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("deactivated model: %s", model.ID)
	return nil
}

// UpdatePricing 更新定价
func (uc *ModelUsecase) UpdatePricing(
	ctx context.Context,
	id string,
	inputPrice, outputPrice float64,
) error {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	model.UpdatePricing(inputPrice, outputPrice)

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update pricing: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Infof("updated pricing for model: %s", model.ID)
	return nil
}

// SetPriority 设置优先级
func (uc *ModelUsecase) SetPriority(ctx context.Context, id string, priority int) error {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if err := model.SetPriority(priority); err != nil {
		return err
	}

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to set priority: %v", err)
		return err
	}

	return nil
}

// SetWeight 设置权重
func (uc *ModelUsecase) SetWeight(ctx context.Context, id string, weight int) error {
	model, err := uc.modelRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if err := model.SetWeight(weight); err != nil {
		return err
	}

	if err := uc.modelRepo.Update(ctx, model); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to set weight: %v", err)
		return err
	}

	return nil
}

// GetModelMetrics 获取模型指标
func (uc *ModelUsecase) GetModelMetrics(ctx context.Context, modelID string) (*domain.ModelMetrics, error) {
	metrics, err := uc.metricsRepo.GetByModelID(ctx, modelID)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to get metrics: %v", err)
		return nil, err
	}
	return metrics, nil
}

// ListAllMetrics 列出所有指标
func (uc *ModelUsecase) ListAllMetrics(ctx context.Context) ([]*domain.ModelMetrics, error) {
	metrics, err := uc.metricsRepo.ListAll(ctx)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("failed to list metrics: %v", err)
		return nil, err
	}
	return metrics, nil
}
