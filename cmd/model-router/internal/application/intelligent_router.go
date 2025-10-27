package application

import (
	"context"
	"fmt"
	"math"
	"sync"
	"time"
)

// RoutingStrategy 路由策略
type RoutingStrategy string

const (
	StrategyRoundRobin    RoutingStrategy = "round_robin"
	StrategyCostOptimized RoutingStrategy = "cost_optimized"
	StrategyLatencyBased  RoutingStrategy = "latency_based"
	StrategyLoadBalanced  RoutingStrategy = "load_balanced"
)

// ModelConfig 模型配置
type ModelConfig struct {
	ID              string
	Name            string
	Provider        string
	Endpoint        string
	Priority        int     // 优先级 (1-10)
	CostPer1KTokens float64 // 每1K tokens成本
	MaxRPS          int     // 最大QPS
	Timeout         time.Duration
	Enabled         bool
}

// ModelHealth 模型健康状态
type ModelHealth struct {
	ModelID         string
	Healthy         bool
	AvgLatencyMs    float64
	ErrorRate       float64
	CurrentRPS      int
	LastCheckTime   time.Time
	ConsecutiveFail int
}

// RoutingRequest 路由请求
type RoutingRequest struct {
	Strategy      RoutingStrategy
	RequiredModel string // 如果指定，直接路由到该模型
	EstTokens     int
	TenantID      string
	Priority      int // 请求优先级
	Context       context.Context
}

// RoutingResult 路由结果
type RoutingResult struct {
	Model            *ModelConfig
	Reason           string // 选择原因
	EstimatedCost    float64
	EstimatedLatency float64
	FallbackUsed     bool
}

// IntelligentRouter 智能路由器
type IntelligentRouter struct {
	models      map[string]*ModelConfig
	health      map[string]*ModelHealth
	modelsMutex sync.RWMutex
	healthMutex sync.RWMutex

	// 轮询计数器
	roundRobinIndex int
	roundRobinMutex sync.Mutex

	// 熔断器
	circuitBreakers map[string]*CircuitBreaker
	breakerMutex    sync.RWMutex
}

// CircuitBreaker 熔断器
type CircuitBreaker struct {
	FailureThreshold int
	RecoveryTimeout  time.Duration
	State            string // closed, open, half_open
	FailureCount     int
	LastFailureTime  time.Time
}

// NewIntelligentRouter 创建智能路由器
func NewIntelligentRouter() *IntelligentRouter {
	return &IntelligentRouter{
		models:          make(map[string]*ModelConfig),
		health:          make(map[string]*ModelHealth),
		circuitBreakers: make(map[string]*CircuitBreaker),
	}
}

// RegisterModel 注册模型
func (r *IntelligentRouter) RegisterModel(model *ModelConfig) {
	r.modelsMutex.Lock()
	defer r.modelsMutex.Unlock()

	r.models[model.ID] = model

	// 初始化健康状态
	r.healthMutex.Lock()
	r.health[model.ID] = &ModelHealth{
		ModelID:       model.ID,
		Healthy:       true,
		LastCheckTime: time.Now(),
	}
	r.healthMutex.Unlock()

	// 初始化熔断器
	r.breakerMutex.Lock()
	r.circuitBreakers[model.ID] = &CircuitBreaker{
		FailureThreshold: 5,
		RecoveryTimeout:  60 * time.Second,
		State:            "closed",
	}
	r.breakerMutex.Unlock()
}

// Route 执行路由决策
func (r *IntelligentRouter) Route(req *RoutingRequest) (*RoutingResult, error) {
	// 1. 如果指定了模型，直接返回
	if req.RequiredModel != "" {
		model, exists := r.getModel(req.RequiredModel)
		if !exists {
			return nil, fmt.Errorf("model not found: %s", req.RequiredModel)
		}

		if !r.isModelAvailable(req.RequiredModel) {
			return nil, fmt.Errorf("model unavailable: %s", req.RequiredModel)
		}

		return &RoutingResult{
			Model:  model,
			Reason: "explicit_model_specified",
		}, nil
	}

	// 2. 根据策略路由
	switch req.Strategy {
	case StrategyRoundRobin:
		return r.routeRoundRobin(req)
	case StrategyCostOptimized:
		return r.routeCostOptimized(req)
	case StrategyLatencyBased:
		return r.routeLatencyBased(req)
	case StrategyLoadBalanced:
		return r.routeLoadBalanced(req)
	default:
		return r.routeLoadBalanced(req)
	}
}

// routeRoundRobin 轮询路由
func (r *IntelligentRouter) routeRoundRobin(req *RoutingRequest) (*RoutingResult, error) {
	availableModels := r.getAvailableModels()
	if len(availableModels) == 0 {
		return nil, fmt.Errorf("no available models")
	}

	r.roundRobinMutex.Lock()
	index := r.roundRobinIndex % len(availableModels)
	r.roundRobinIndex++
	r.roundRobinMutex.Unlock()

	selectedModel := availableModels[index]

	return &RoutingResult{
		Model:  selectedModel,
		Reason: "round_robin",
	}, nil
}

// routeCostOptimized 成本优化路由
func (r *IntelligentRouter) routeCostOptimized(req *RoutingRequest) (*RoutingResult, error) {
	availableModels := r.getAvailableModels()
	if len(availableModels) == 0 {
		return nil, fmt.Errorf("no available models")
	}

	// 按成本排序，选择最便宜的
	var bestModel *ModelConfig
	minCost := math.MaxFloat64

	for _, model := range availableModels {
		if model.CostPer1KTokens < minCost {
			minCost = model.CostPer1KTokens
			bestModel = model
		}
	}

	if bestModel == nil {
		return nil, fmt.Errorf("no suitable model found")
	}

	estimatedCost := (float64(req.EstTokens) / 1000.0) * bestModel.CostPer1KTokens

	return &RoutingResult{
		Model:         bestModel,
		Reason:        "lowest_cost",
		EstimatedCost: estimatedCost,
	}, nil
}

// routeLatencyBased 基于延迟的路由
func (r *IntelligentRouter) routeLatencyBased(req *RoutingRequest) (*RoutingResult, error) {
	availableModels := r.getAvailableModels()
	if len(availableModels) == 0 {
		return nil, fmt.Errorf("no available models")
	}

	r.healthMutex.RLock()
	defer r.healthMutex.RUnlock()

	var bestModel *ModelConfig
	minLatency := math.MaxFloat64

	for _, model := range availableModels {
		health, exists := r.health[model.ID]
		if exists && health.AvgLatencyMs < minLatency {
			minLatency = health.AvgLatencyMs
			bestModel = model
		}
	}

	if bestModel == nil {
		// 回退到第一个可用模型
		bestModel = availableModels[0]
		minLatency = 100 // 默认估计
	}

	return &RoutingResult{
		Model:            bestModel,
		Reason:           "lowest_latency",
		EstimatedLatency: minLatency,
	}, nil
}

// routeLoadBalanced 负载均衡路由
func (r *IntelligentRouter) routeLoadBalanced(req *RoutingRequest) (*RoutingResult, error) {
	availableModels := r.getAvailableModels()
	if len(availableModels) == 0 {
		return nil, fmt.Errorf("no available models")
	}

	r.healthMutex.RLock()
	defer r.healthMutex.RUnlock()

	// 计算每个模型的负载分数（综合考虑RPS、错误率、延迟）
	type modelScore struct {
		model *ModelConfig
		score float64
	}

	scores := make([]modelScore, 0, len(availableModels))

	for _, model := range availableModels {
		health, exists := r.health[model.ID]
		if !exists {
			continue
		}

		// 计算负载分数（越低越好）
		rpsUtilization := float64(health.CurrentRPS) / float64(model.MaxRPS)
		errorPenalty := health.ErrorRate * 10
		latencyPenalty := health.AvgLatencyMs / 1000.0

		score := rpsUtilization + errorPenalty + latencyPenalty

		scores = append(scores, modelScore{
			model: model,
			score: score,
		})
	}

	if len(scores) == 0 {
		return nil, fmt.Errorf("no suitable model found")
	}

	// 选择分数最低的
	bestScore := scores[0]
	for _, s := range scores[1:] {
		if s.score < bestScore.score {
			bestScore = s
		}
	}

	return &RoutingResult{
		Model:  bestScore.model,
		Reason: fmt.Sprintf("load_balanced_score_%.2f", bestScore.score),
	}, nil
}

// getAvailableModels 获取所有可用模型
func (r *IntelligentRouter) getAvailableModels() []*ModelConfig {
	r.modelsMutex.RLock()
	defer r.modelsMutex.RUnlock()

	available := make([]*ModelConfig, 0)

	for _, model := range r.models {
		if model.Enabled && r.isModelAvailable(model.ID) {
			available = append(available, model)
		}
	}

	return available
}

// isModelAvailable 检查模型是否可用
func (r *IntelligentRouter) isModelAvailable(modelID string) bool {
	// 检查健康状态
	r.healthMutex.RLock()
	health, exists := r.health[modelID]
	r.healthMutex.RUnlock()

	if !exists || !health.Healthy {
		return false
	}

	// 检查熔断器
	r.breakerMutex.RLock()
	breaker, exists := r.circuitBreakers[modelID]
	r.breakerMutex.RUnlock()

	if exists && breaker.State == "open" {
		// 检查是否可以恢复
		if time.Since(breaker.LastFailureTime) > breaker.RecoveryTimeout {
			r.breakerMutex.Lock()
			breaker.State = "half_open"
			r.breakerMutex.Unlock()
			return true
		}
		return false
	}

	return true
}

// getModel 获取模型配置
func (r *IntelligentRouter) getModel(modelID string) (*ModelConfig, bool) {
	r.modelsMutex.RLock()
	defer r.modelsMutex.RUnlock()

	model, exists := r.models[modelID]
	return model, exists
}

// ReportSuccess 报告成功请求
func (r *IntelligentRouter) ReportSuccess(modelID string, latencyMs float64) {
	r.healthMutex.Lock()
	defer r.healthMutex.Unlock()

	health, exists := r.health[modelID]
	if !exists {
		return
	}

	// 更新平均延迟（指数移动平均）
	alpha := 0.2
	health.AvgLatencyMs = alpha*latencyMs + (1-alpha)*health.AvgLatencyMs
	health.Healthy = true
	health.LastCheckTime = time.Now()
	health.ConsecutiveFail = 0

	// 重置熔断器
	r.breakerMutex.Lock()
	if breaker, exists := r.circuitBreakers[modelID]; exists {
		breaker.FailureCount = 0
		breaker.State = "closed"
	}
	r.breakerMutex.Unlock()
}

// ReportFailure 报告失败请求
func (r *IntelligentRouter) ReportFailure(modelID string) {
	r.healthMutex.Lock()
	health, exists := r.health[modelID]
	if exists {
		health.ConsecutiveFail++
		if health.ConsecutiveFail >= 3 {
			health.Healthy = false
		}
	}
	r.healthMutex.Unlock()

	// 更新熔断器
	r.breakerMutex.Lock()
	defer r.breakerMutex.Unlock()

	breaker, exists := r.circuitBreakers[modelID]
	if !exists {
		return
	}

	breaker.FailureCount++
	breaker.LastFailureTime = time.Now()

	if breaker.FailureCount >= breaker.FailureThreshold {
		breaker.State = "open"
	}
}

// UpdateHealth 更新模型健康状态
func (r *IntelligentRouter) UpdateHealth(modelID string, health *ModelHealth) {
	r.healthMutex.Lock()
	defer r.healthMutex.Unlock()

	r.health[modelID] = health
}

// GetStats 获取路由器统计信息
func (r *IntelligentRouter) GetStats() map[string]interface{} {
	r.modelsMutex.RLock()
	r.healthMutex.RLock()
	defer r.modelsMutex.RUnlock()
	defer r.healthMutex.RUnlock()

	stats := make(map[string]interface{})

	stats["total_models"] = len(r.models)

	healthyCount := 0
	for _, health := range r.health {
		if health.Healthy {
			healthyCount++
		}
	}
	stats["healthy_models"] = healthyCount

	// 各模型的健康状态
	modelStats := make([]map[string]interface{}, 0)
	for id, health := range r.health {
		model, exists := r.models[id]
		if !exists {
			continue
		}

		modelStats = append(modelStats, map[string]interface{}{
			"id":               id,
			"name":             model.Name,
			"healthy":          health.Healthy,
			"avg_latency_ms":   health.AvgLatencyMs,
			"error_rate":       health.ErrorRate,
			"current_rps":      health.CurrentRPS,
			"consecutive_fail": health.ConsecutiveFail,
		})
	}
	stats["models"] = modelStats

	return stats
}
