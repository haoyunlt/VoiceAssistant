package biz

import (
	"context"
	"fmt"
	"math/rand"
	"sort"
	"sync"

	"voicehelper/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// RouterUsecase 路由用例
type RouterUsecase struct {
	modelRepo       domain.ModelRepository
	metricsRepo     domain.ModelMetricsRepository
	roundRobinIndex map[string]int
	mu              sync.Mutex
	log             *log.Helper
}

// NewRouterUsecase 创建路由用例
func NewRouterUsecase(
	modelRepo domain.ModelRepository,
	metricsRepo domain.ModelMetricsRepository,
	logger log.Logger,
) *RouterUsecase {
	return &RouterUsecase{
		modelRepo:       modelRepo,
		metricsRepo:     metricsRepo,
		roundRobinIndex: make(map[string]int),
		log:             log.NewHelper(logger),
	}
}

// Route 路由请求
func (uc *RouterUsecase) Route(
	ctx context.Context,
	req *domain.RouteRequest,
) (*domain.RouteResult, error) {
	// 获取可用模型列表
	models, err := uc.modelRepo.ListAvailable(ctx, req.ModelType)
	if err != nil {
		return nil, err
	}

	if len(models) == 0 {
		return nil, domain.ErrNoAvailableModel
	}

	// 过滤：根据能力要求
	models = uc.filterByCapabilities(models, req.RequiredCapabilities)
	if len(models) == 0 {
		return nil, domain.ErrCapabilityNotSupported
	}

	// 过滤：根据偏好提供商
	if req.PreferredProvider != "" {
		preferredModels := uc.filterByProvider(models, req.PreferredProvider)
		if len(preferredModels) > 0 {
			models = preferredModels
		}
	}

	// 根据策略选择模型
	var selectedModel *domain.Model
	var reason string

	switch req.Strategy {
	case domain.StrategyPriority:
		selectedModel, reason = uc.selectByPriority(models)
	case domain.StrategyRoundRobin:
		selectedModel, reason = uc.selectByRoundRobin(models, string(req.ModelType))
	case domain.StrategyWeighted:
		selectedModel, reason = uc.selectByWeight(models)
	case domain.StrategyLeastLatency:
		selectedModel, reason = uc.selectByLeastLatency(ctx, models)
	case domain.StrategyLeastCost:
		selectedModel, reason = uc.selectByLeastCost(models)
	case domain.StrategyRandom:
		selectedModel, reason = uc.selectRandom(models)
	default:
		selectedModel, reason = uc.selectByPriority(models)
	}

	if selectedModel == nil {
		return nil, domain.ErrNoAvailableModel
	}

	// 构建结果
	result := domain.NewRouteResult(req.ID, selectedModel, req.Strategy, reason)

	// 添加备选模型（排除已选中的）
	for _, m := range models {
		if m.ID != selectedModel.ID {
			result.AlternativeModels = append(result.AlternativeModels, m)
		}
	}

	uc.log.WithContext(ctx).Infof(
		"routed request %s to model %s (%s), strategy: %s, reason: %s",
		req.ID,
		selectedModel.ID,
		selectedModel.Name,
		req.Strategy,
		reason,
	)

	return result, nil
}

// RecordRequest 记录请求结果
func (uc *RouterUsecase) RecordRequest(
	ctx context.Context,
	modelID string,
	success bool,
	latencyMs int,
	inputTokens, outputTokens int,
) error {
	// 获取模型
	model, err := uc.modelRepo.GetByID(ctx, modelID)
	if err != nil {
		return err
	}

	// 计算成本
	cost := model.CalculateCost(inputTokens, outputTokens)
	totalTokens := inputTokens + outputTokens

	// 更新指标
	if err := uc.metricsRepo.UpdateMetrics(ctx, modelID, success, latencyMs, totalTokens, cost); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update metrics: %v", err)
		return err
	}

	uc.log.WithContext(ctx).Debugf(
		"recorded request for model %s: success=%v, latency=%dms, tokens=%d, cost=$%.4f",
		modelID,
		success,
		latencyMs,
		totalTokens,
		cost,
	)

	return nil
}

// filterByCapabilities 根据能力过滤
func (uc *RouterUsecase) filterByCapabilities(models []*domain.Model, capabilities []string) []*domain.Model {
	if len(capabilities) == 0 {
		return models
	}

	filtered := make([]*domain.Model, 0)
	for _, model := range models {
		hasAll := true
		for _, cap := range capabilities {
			if !model.HasCapability(cap) {
				hasAll = false
				break
			}
		}
		if hasAll {
			filtered = append(filtered, model)
		}
	}
	return filtered
}

// filterByProvider 根据提供商过滤
func (uc *RouterUsecase) filterByProvider(models []*domain.Model, provider domain.ModelProvider) []*domain.Model {
	filtered := make([]*domain.Model, 0)
	for _, model := range models {
		if model.Provider == provider {
			filtered = append(filtered, model)
		}
	}
	return filtered
}

// selectByPriority 按优先级选择
func (uc *RouterUsecase) selectByPriority(models []*domain.Model) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	// 按优先级降序排序
	sort.Slice(models, func(i, j int) bool {
		return models[i].Priority > models[j].Priority
	})

	return models[0], fmt.Sprintf("highest priority: %d", models[0].Priority)
}

// selectByRoundRobin 轮询选择
func (uc *RouterUsecase) selectByRoundRobin(models []*domain.Model, key string) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	uc.mu.Lock()
	defer uc.mu.Unlock()

	index := uc.roundRobinIndex[key]
	selected := models[index%len(models)]
	uc.roundRobinIndex[key] = (index + 1) % len(models)

	return selected, "round robin"
}

// selectByWeight 加权选择
func (uc *RouterUsecase) selectByWeight(models []*domain.Model) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	// 计算总权重
	totalWeight := 0
	for _, model := range models {
		totalWeight += model.Weight
	}

	if totalWeight == 0 {
		return models[0], "default (zero weight)"
	}

	// 加权随机选择
	random := rand.Intn(totalWeight)
	cumulative := 0
	for _, model := range models {
		cumulative += model.Weight
		if random < cumulative {
			return model, fmt.Sprintf("weighted: %d/%d", model.Weight, totalWeight)
		}
	}

	return models[0], "fallback"
}

// selectByLeastLatency 按最低延迟选择
func (uc *RouterUsecase) selectByLeastLatency(ctx context.Context, models []*domain.Model) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	// 获取所有模型的指标
	metricsMap := make(map[string]*domain.ModelMetrics)
	for _, model := range models {
		metrics, err := uc.metricsRepo.GetByModelID(ctx, model.ID)
		if err == nil {
			metricsMap[model.ID] = metrics
		}
	}

	// 选择延迟最低的
	var selected *domain.Model
	minLatency := float64(999999)

	for _, model := range models {
		if metrics, exists := metricsMap[model.ID]; exists {
			if metrics.AvgLatencyMs < minLatency {
				minLatency = metrics.AvgLatencyMs
				selected = model
			}
		}
	}

	if selected == nil {
		return models[0], "no metrics, fallback to first"
	}

	return selected, fmt.Sprintf("lowest latency: %.2fms", minLatency)
}

// selectByLeastCost 按最低成本选择
func (uc *RouterUsecase) selectByLeastCost(models []*domain.Model) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	// 按平均价格排序（输入+输出平均）
	sort.Slice(models, func(i, j int) bool {
		avgI := (models[i].InputPricePerK + models[i].OutputPricePerK) / 2.0
		avgJ := (models[j].InputPricePerK + models[j].OutputPricePerK) / 2.0
		return avgI < avgJ
	})

	selected := models[0]
	avgPrice := (selected.InputPricePerK + selected.OutputPricePerK) / 2.0

	return selected, fmt.Sprintf("lowest cost: $%.4f/1K", avgPrice)
}

// selectRandom 随机选择
func (uc *RouterUsecase) selectRandom(models []*domain.Model) (*domain.Model, string) {
	if len(models) == 0 {
		return nil, ""
	}

	index := rand.Intn(len(models))
	return models[index], "random"
}

// GetHealthyModels 获取健康的模型
func (uc *RouterUsecase) GetHealthyModels(ctx context.Context, modelType domain.ModelType) ([]*domain.Model, error) {
	// 获取所有可用模型
	models, err := uc.modelRepo.ListAvailable(ctx, modelType)
	if err != nil {
		return nil, err
	}

	// 过滤健康的模型
	healthy := make([]*domain.Model, 0)
	for _, model := range models {
		metrics, err := uc.metricsRepo.GetByModelID(ctx, model.ID)
		if err != nil {
			// 没有指标数据，视为健康
			healthy = append(healthy, model)
			continue
		}

		if metrics.IsHealthy() {
			healthy = append(healthy, model)
		}
	}

	return healthy, nil
}
