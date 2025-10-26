package application

import (
	"context"
	"fmt"
	"math/rand"
	"sort"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"
)

// RoutingStrategy 路由策略
type RoutingStrategy string

const (
	StrategyCheapest      RoutingStrategy = "cheapest"       // 成本最低
	StrategyFastest       RoutingStrategy = "fastest"        // 延迟最低
	StrategyMostAvailable RoutingStrategy = "most_available" // 可用性最高
	StrategyBestQuality   RoutingStrategy = "best_quality"   // 质量最高
	StrategyRoundRobin    RoutingStrategy = "round_robin"    // 轮询
	StrategyRandom        RoutingStrategy = "random"         // 随机
)

// RoutingRequest 路由请求
type RoutingRequest struct {
	// 必选参数
	Prompt    string          `json:"prompt"`     // 提示词
	MaxTokens int             `json:"max_tokens"` // 最大生成token数
	Strategy  RoutingStrategy `json:"strategy"`   // 路由策略

	// 可选参数
	Capability       *domain.ModelCapability `json:"capability"`         // 需要的能力
	Provider         *domain.ModelProvider   `json:"provider"`           // 指定提供商
	MinContextLength int                     `json:"min_context_length"` // 最小上下文长度
	MaxCost          *float64                `json:"max_cost"`           // 最大成本限制
	MaxLatency       *time.Duration          `json:"max_latency"`        // 最大延迟限制

	// 偏好设置
	Temperature float64 `json:"temperature"` // 温度
	Streaming   bool    `json:"streaming"`   // 是否流式
}

// RoutingResponse 路由响应
type RoutingResponse struct {
	ModelID          string               `json:"model_id"`          // 选中的模型ID
	ModelName        string               `json:"model_name"`        // 模型名称
	Provider         domain.ModelProvider `json:"provider"`          // 提供商
	EstimatedCost    float64              `json:"estimated_cost"`    // 预估成本
	EstimatedLatency time.Duration        `json:"estimated_latency"` // 预估延迟
	Reason           string               `json:"reason"`            // 选择原因
}

// RoutingService 路由服务
type RoutingService struct {
	registry      *domain.ModelRegistry
	roundRobinIdx map[string]int // provider -> index (用于轮询)
}

// NewRoutingService 创建路由服务
func NewRoutingService(registry *domain.ModelRegistry) *RoutingService {
	return &RoutingService{
		registry:      registry,
		roundRobinIdx: make(map[string]int),
	}
}

// Route 执行路由决策
func (s *RoutingService) Route(ctx context.Context, req *RoutingRequest) (*RoutingResponse, error) {
	// 1. 获取候选模型
	candidates, err := s.getCandidates(req)
	if err != nil {
		return nil, err
	}

	if len(candidates) == 0 {
		return nil, fmt.Errorf("no available models found for the request")
	}

	// 2. 根据策略选择模型
	var selected *domain.ModelInfo
	var reason string

	switch req.Strategy {
	case StrategyCheapest:
		selected, reason = s.selectCheapest(candidates, req)
	case StrategyFastest:
		selected, reason = s.selectFastest(candidates)
	case StrategyMostAvailable:
		selected, reason = s.selectMostAvailable(candidates)
	case StrategyBestQuality:
		selected, reason = s.selectBestQuality(candidates)
	case StrategyRoundRobin:
		selected, reason = s.selectRoundRobin(candidates, req)
	case StrategyRandom:
		selected, reason = s.selectRandom(candidates)
	default:
		return nil, fmt.Errorf("unknown routing strategy: %s", req.Strategy)
	}

	if selected == nil {
		return nil, fmt.Errorf("failed to select a model")
	}

	// 3. 估算输入token数 (粗略估算: 1 token ≈ 4 字符)
	estimatedInputTokens := len(req.Prompt) / 4

	// 4. 构建响应
	return &RoutingResponse{
		ModelID:          selected.ModelID,
		ModelName:        selected.ModelName,
		Provider:         selected.Provider,
		EstimatedCost:    selected.EstimateCost(estimatedInputTokens, req.MaxTokens),
		EstimatedLatency: selected.AvgLatency,
		Reason:           reason,
	}, nil
}

// getCandidates 获取候选模型
func (s *RoutingService) getCandidates(req *RoutingRequest) ([]*domain.ModelInfo, error) {
	var candidates []*domain.ModelInfo

	// 1. 获取所有启用的模型
	allModels := s.registry.ListAll()

	// 2. 应用过滤条件
	for _, model := range allModels {
		// 检查健康状态
		if !model.IsHealthy() {
			continue
		}

		// 检查提供商
		if req.Provider != nil && model.Provider != *req.Provider {
			continue
		}

		// 检查能力
		if req.Capability != nil && !model.HasCapability(*req.Capability) {
			continue
		}

		// 检查流式能力
		if req.Streaming && !model.HasCapability(domain.CapabilityStreaming) {
			continue
		}

		// 检查上下文长度
		if req.MinContextLength > 0 && model.ContextLength < req.MinContextLength {
			continue
		}

		// 检查成本限制
		if req.MaxCost != nil {
			estimatedInputTokens := len(req.Prompt) / 4
			estimatedCost := model.EstimateCost(estimatedInputTokens, req.MaxTokens)
			if estimatedCost > *req.MaxCost {
				continue
			}
		}

		// 检查延迟限制
		if req.MaxLatency != nil && model.AvgLatency > *req.MaxLatency {
			continue
		}

		candidates = append(candidates, model)
	}

	return candidates, nil
}

// selectCheapest 选择成本最低的模型
func (s *RoutingService) selectCheapest(candidates []*domain.ModelInfo, req *RoutingRequest) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	estimatedInputTokens := len(req.Prompt) / 4

	sort.Slice(candidates, func(i, j int) bool {
		costI := candidates[i].EstimateCost(estimatedInputTokens, req.MaxTokens)
		costJ := candidates[j].EstimateCost(estimatedInputTokens, req.MaxTokens)
		return costI < costJ
	})

	selected := candidates[0]
	cost := selected.EstimateCost(estimatedInputTokens, req.MaxTokens)

	return selected, fmt.Sprintf("Cheapest model (estimated cost: $%.6f)", cost)
}

// selectFastest 选择延迟最低的模型
func (s *RoutingService) selectFastest(candidates []*domain.ModelInfo) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].AvgLatency < candidates[j].AvgLatency
	})

	selected := candidates[0]

	return selected, fmt.Sprintf("Fastest model (avg latency: %v)", selected.AvgLatency)
}

// selectMostAvailable 选择可用性最高的模型
func (s *RoutingService) selectMostAvailable(candidates []*domain.ModelInfo) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].Availability > candidates[j].Availability
	})

	selected := candidates[0]

	return selected, fmt.Sprintf("Most available model (availability: %.2f%%)", selected.Availability*100)
}

// selectBestQuality 选择质量最高的模型 (综合评分)
func (s *RoutingService) selectBestQuality(candidates []*domain.ModelInfo) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	// 计算质量分数 (可用性权重40%, 低错误率权重30%, 上下文长度权重30%)
	type scored struct {
		model *domain.ModelInfo
		score float64
	}

	var scored []scored
	for _, model := range candidates {
		score := model.Availability*0.4 + (1-model.ErrorRate)*0.3 + float64(model.ContextLength)/200000.0*0.3
		scored = append(scored, scored{model: model, score: score})
	}

	sort.Slice(scored, func(i, j int) bool {
		return scored[i].score > scored[j].score
	})

	selected := scored[0].model

	return selected, fmt.Sprintf("Best quality model (score: %.2f)", scored[0].score)
}

// selectRoundRobin 轮询选择
func (s *RoutingService) selectRoundRobin(candidates []*domain.ModelInfo, req *RoutingRequest) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	// 按提供商分组
	key := "all"
	if req.Provider != nil {
		key = string(*req.Provider)
	}

	idx := s.roundRobinIdx[key] % len(candidates)
	selected := candidates[idx]

	s.roundRobinIdx[key] = (idx + 1) % len(candidates)

	return selected, "Round-robin selection"
}

// selectRandom 随机选择
func (s *RoutingService) selectRandom(candidates []*domain.ModelInfo) (*domain.ModelInfo, string) {
	if len(candidates) == 0 {
		return nil, ""
	}

	rand.Seed(time.Now().UnixNano())
	idx := rand.Intn(len(candidates))
	selected := candidates[idx]

	return selected, "Random selection"
}

// GetModelInfo 获取模型信息
func (s *RoutingService) GetModelInfo(modelID string) (*domain.ModelInfo, error) {
	return s.registry.Get(modelID)
}

// ListModels 列出所有模型
func (s *RoutingService) ListModels() []*domain.ModelInfo {
	return s.registry.ListAll()
}
