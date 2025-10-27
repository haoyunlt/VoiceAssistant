package service

import (
	"context"

	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/domain"
)

// ModelRouterService 模型路由服务
type ModelRouterService struct {
	routingService  *application.RoutingService
	costOptimizer   *application.CostOptimizer
	fallbackManager *application.FallbackManager
}

// NewModelRouterService 创建模型路由服务
func NewModelRouterService(
	routingService *application.RoutingService,
	costOptimizer *application.CostOptimizer,
	fallbackManager *application.FallbackManager,
) *ModelRouterService {
	return &ModelRouterService{
		routingService:  routingService,
		costOptimizer:   costOptimizer,
		fallbackManager: fallbackManager,
	}
}

// Route 执行路由决策
func (s *ModelRouterService) Route(ctx context.Context, req *application.RoutingRequest) (*application.RoutingResponse, error) {
	// 1. 执行路由决策
	response, err := s.routingService.Route(ctx, req)
	if err != nil {
		return nil, err
	}

	// 2. 成本优化（可选）
	if s.costOptimizer != nil {
		// 获取选中的模型
		selectedModel, err := s.routingService.GetModelInfo(response.ModelID)
		if err == nil {
			// 尝试优化
			optimizedModel, err := s.costOptimizer.OptimizeRoute(ctx, req, selectedModel)
			if err == nil && optimizedModel != nil && optimizedModel.ModelID != selectedModel.ModelID {
				// 使用优化后的模型
				estimatedInputTokens := len(req.Prompt) / 4
				response = &application.RoutingResponse{
					ModelID:          optimizedModel.ModelID,
					ModelName:        optimizedModel.ModelName,
					Provider:         optimizedModel.Provider,
					EstimatedCost:    optimizedModel.EstimateCost(estimatedInputTokens, req.MaxTokens),
					EstimatedLatency: optimizedModel.AvgLatency,
					Reason:           "Cost optimized: " + response.Reason,
				}
			}
		}
	}

	return response, nil
}

// ListModels 列出所有可用模型
func (s *ModelRouterService) ListModels(ctx context.Context) []*domain.ModelInfo {
	return s.routingService.ListModels()
}

// GetModelInfo 获取模型信息
func (s *ModelRouterService) GetModelInfo(ctx context.Context, modelID string) (*domain.ModelInfo, error) {
	return s.routingService.GetModelInfo(modelID)
}

// RecordUsage 记录使用情况
func (s *ModelRouterService) RecordUsage(
	ctx context.Context,
	modelID string,
	inputTokens int,
	outputTokens int,
	success bool,
	latency int64,
) error {
	// 1. 更新模型性能指标
	if err := s.routingService.registry.UpdateMetrics(
		modelID,
		latency,
		success,
	); err != nil {
		return err
	}

	// 2. 记录成本
	if s.costOptimizer != nil {
		model, err := s.routingService.GetModelInfo(modelID)
		if err == nil {
			cost := model.EstimateCost(inputTokens, outputTokens)
			_ = s.costOptimizer.RecordUsage(modelID, inputTokens, outputTokens, cost)
		}
	}

	// 3. 更新熔断器状态
	if s.fallbackManager != nil {
		if success {
			s.fallbackManager.recordSuccess(modelID)
		} else {
			s.fallbackManager.recordFailure(modelID)
		}
	}

	return nil
}

// GetUsageStats 获取使用统计
func (s *ModelRouterService) GetUsageStats(ctx context.Context) *application.UsageStats {
	if s.costOptimizer == nil {
		return nil
	}
	return s.costOptimizer.GetUsageStats()
}

// GetRecommendations 获取优化建议
func (s *ModelRouterService) GetRecommendations(ctx context.Context) []*application.OptimizationRecommendation {
	if s.costOptimizer == nil {
		return nil
	}
	return s.costOptimizer.GetRecommendations()
}

// GetCircuitStates 获取所有熔断器状态
func (s *ModelRouterService) GetCircuitStates(ctx context.Context) map[string]application.CircuitState {
	if s.fallbackManager == nil {
		return nil
	}
	return s.fallbackManager.GetAllCircuitStates()
}

// PredictCost 预测成本
func (s *ModelRouterService) PredictCost(
	ctx context.Context,
	modelID string,
	inputTokens int,
	outputTokens int,
) (float64, error) {
	if s.costOptimizer == nil {
		model, err := s.routingService.GetModelInfo(modelID)
		if err != nil {
			return 0, err
		}
		return model.EstimateCost(inputTokens, outputTokens), nil
	}
	return s.costOptimizer.PredictCost(modelID, inputTokens, outputTokens)
}

// CompareCosts 比较多个模型的成本
func (s *ModelRouterService) CompareCosts(
	ctx context.Context,
	modelIDs []string,
	inputTokens int,
	outputTokens int,
) (map[string]float64, error) {
	if s.costOptimizer == nil {
		costs := make(map[string]float64)
		for _, modelID := range modelIDs {
			model, err := s.routingService.GetModelInfo(modelID)
			if err != nil {
				continue
			}
			costs[modelID] = model.EstimateCost(inputTokens, outputTokens)
		}
		return costs, nil
	}
	return s.costOptimizer.CompareCosts(modelIDs, inputTokens, outputTokens)
}
