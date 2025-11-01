package application

import (
	"context"
	"fmt"
	"time"

	"voicehelper/cmd/model-router/internal/domain"
	"voicehelper/pkg/clients/algo"
)

// ModelExecutionService 模型执行服务
// 负责将路由结果转换为实际的模型调用
type ModelExecutionService struct {
	algoClientManager *algo.ClientManager
}

// NewModelExecutionService 创建模型执行服务
func NewModelExecutionService(algoClientManager *algo.ClientManager) *ModelExecutionService {
	return &ModelExecutionService{
		algoClientManager: algoClientManager,
	}
}

// ModelRequest 模型请求
type ModelRequest struct {
	Model       string                   `json:"model"`
	Messages    []map[string]interface{} `json:"messages"`
	Temperature float64                  `json:"temperature,omitempty"`
	MaxTokens   int                      `json:"max_tokens,omitempty"`
	Stream      bool                     `json:"stream,omitempty"`
}

// ModelResponse 模型响应
type ModelResponse struct {
	ID      string                 `json:"id"`
	Object  string                 `json:"object"`
	Created int64                  `json:"created"`
	Model   string                 `json:"model"`
	Choices []ModelChoice          `json:"choices"`
	Usage   ModelUsage             `json:"usage"`
	Meta    map[string]interface{} `json:"meta,omitempty"`
}

// ModelChoice 模型选择
type ModelChoice struct {
	Index        int                    `json:"index"`
	Message      map[string]interface{} `json:"message"`
	FinishReason string                 `json:"finish_reason"`
}

// ModelUsage Token 使用量
type ModelUsage struct {
	PromptTokens     int     `json:"prompt_tokens"`
	CompletionTokens int     `json:"completion_tokens"`
	TotalTokens      int     `json:"total_tokens"`
	CostUSD          float64 `json:"cost_usd,omitempty"`
}

// ExecuteModelRequest 执行模型请求（带路由选择）
func (s *ModelExecutionService) ExecuteModelRequest(
	ctx context.Context,
	routedModel *domain.RouteResult,
	request *ModelRequest,
) (*ModelResponse, error) {
	// 检查 model-adapter 是否健康
	if !s.algoClientManager.IsServiceHealthy("model-adapter") {
		// 尝试降级到备选模型
		if len(routedModel.AlternativeModels) > 0 {
			return s.executeWithFallback(ctx, routedModel.AlternativeModels, request)
		}
		return nil, fmt.Errorf("model-adapter is not available")
	}

	// 使用路由选择的模型
	request.Model = routedModel.SelectedModel.ID

	// 调用 model-adapter
	adapterClient := s.algoClientManager.ModelAdapter

	var result map[string]interface{}
	err := adapterClient.Post(ctx, "/api/v1/chat/completions", request, &result)
	if err != nil {
		// 调用失败，尝试降级
		if len(routedModel.AlternativeModels) > 0 {
			return s.executeWithFallback(ctx, routedModel.AlternativeModels, request)
		}
		return nil, fmt.Errorf("model execution failed: %w", err)
	}

	// 解析响应
	response := parseModelResponse(result)

	// 添加路由元数据
	if response.Meta == nil {
		response.Meta = make(map[string]interface{})
	}
	response.Meta["routing_strategy"] = string(routedModel.Strategy)
	response.Meta["routing_reason"] = routedModel.Reason
	response.Meta["selected_model"] = routedModel.SelectedModel.ID
	response.Meta["provider"] = routedModel.SelectedModel.Provider

	return response, nil
}

// executeWithFallback 使用备选模型执行请求
func (s *ModelExecutionService) executeWithFallback(
	ctx context.Context,
	alternatives []*domain.Model,
	request *ModelRequest,
) (*ModelResponse, error) {
	for i, model := range alternatives {
		// 更新请求的模型
		request.Model = model.ID

		var result map[string]interface{}
		err := s.algoClientManager.ModelAdapter.Post(ctx, "/api/v1/chat/completions", request, &result)
		if err == nil {
			response := parseModelResponse(result)
			// 添加降级标记
			if response.Meta == nil {
				response.Meta = make(map[string]interface{})
			}
			response.Meta["fallback"] = true
			response.Meta["fallback_attempt"] = i + 1
			response.Meta["fallback_model"] = model.ID
			return response, nil
		}

		// 最后一个备选也失败了
		if i == len(alternatives)-1 {
			return nil, fmt.Errorf("all fallback models failed: %w", err)
		}
	}

	return nil, fmt.Errorf("no fallback models available")
}

// ExecuteWithBestCost 使用成本最优的模型执行
func (s *ModelExecutionService) ExecuteWithBestCost(
	ctx context.Context,
	request *ModelRequest,
	maxCostUSD float64,
) (*ModelResponse, error) {
	// 根据成本限制路由
	routingRequest := &domain.RouteRequest{
		ModelType:  domain.ModelTypeLLM,
		Strategy:   domain.StrategyLeastCost,
		MaxBudget:  maxCostUSD,
		TenantID:   extractTenantID(ctx),
		RequestID:  extractRequestID(ctx),
	}

	// 这里应该调用 RouterUsecase.Route，但为了简化，直接使用 model-adapter
	// TODO: 集成 RouterUsecase

	return s.ExecuteModelRequest(ctx, &domain.RouteResult{
		SelectedModel: &domain.Model{
			ID:       "gpt-3.5-turbo",
			Provider: "openai",
		},
		Strategy: domain.StrategyLeastCost,
		Reason:   "cost-optimized selection",
	}, request)
}

// parseModelResponse 解析模型响应
func parseModelResponse(data map[string]interface{}) *ModelResponse {
	response := &ModelResponse{
		Created: time.Now().Unix(),
		Object:  "chat.completion",
	}

	if id, ok := data["id"].(string); ok {
		response.ID = id
	}
	if model, ok := data["model"].(string); ok {
		response.Model = model
	}

	// 解析 choices
	if choices, ok := data["choices"].([]interface{}); ok {
		for _, choice := range choices {
			if choiceMap, ok := choice.(map[string]interface{}); ok {
				c := ModelChoice{}
				if idx, ok := choiceMap["index"].(float64); ok {
					c.Index = int(idx)
				}
				if msg, ok := choiceMap["message"].(map[string]interface{}); ok {
					c.Message = msg
				}
				if reason, ok := choiceMap["finish_reason"].(string); ok {
					c.FinishReason = reason
				}
				response.Choices = append(response.Choices, c)
			}
		}
	}

	// 解析 usage
	if usage, ok := data["usage"].(map[string]interface{}); ok {
		if prompt, ok := usage["prompt_tokens"].(float64); ok {
			response.Usage.PromptTokens = int(prompt)
		}
		if completion, ok := usage["completion_tokens"].(float64); ok {
			response.Usage.CompletionTokens = int(completion)
		}
		if total, ok := usage["total_tokens"].(float64); ok {
			response.Usage.TotalTokens = int(total)
		}
		if cost, ok := usage["cost_usd"].(float64); ok {
			response.Usage.CostUSD = cost
		}
	}

	return response
}

// Helper functions

func extractTenantID(ctx context.Context) string {
	// TODO: 从 context 中提取租户 ID
	return "default"
}

func extractRequestID(ctx context.Context) string {
	// TODO: 从 context 中提取请求 ID
	return fmt.Sprintf("req-%d", time.Now().UnixNano())
}
