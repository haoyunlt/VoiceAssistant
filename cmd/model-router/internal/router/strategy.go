package router

import (
	"context"
	"errors"
	"fmt"
	"math"
	"sync"
	"time"
)

// RoutingStrategy 路由策略
type RoutingStrategy string

const (
	StrategyCost        RoutingStrategy = "cost"        // 成本优先
	StrategyPerformance RoutingStrategy = "performance" // 性能优先
	StrategyBalanced    RoutingStrategy = "balanced"    // 平衡模式
)

// ModelConfig 模型配置
type ModelConfig struct {
	Name              string  `json:"name"`
	Provider          string  `json:"provider"`           // openai, anthropic, etc.
	Endpoint          string  `json:"endpoint"`           // model-adapter URL
	CostPer1kTokens   float64 `json:"cost_per_1k_tokens"` // 每1k tokens成本
	Weight            float64 `json:"weight"`             // 权重（用于负载均衡）
	MaxConcurrent     int     `json:"max_concurrent"`     // 最大并发数
	Priority          int     `json:"priority"`           // 优先级（越小越优先）
	AvgResponseTimeMs float64 `json:"avg_response_time_ms"`
}

// ModelStats 模型统计
type ModelStats struct {
	TotalRequests   int64
	SuccessRequests int64
	FailedRequests  int64
	TotalTokens     int64
	TotalCost       float64
	CurrentLoad     int32 // 当前负载
	AvgLatencyMs    float64
	LastUpdateTime  time.Time
	mu              sync.RWMutex
}

// Router 模型路由器
type Router struct {
	models   map[string]*ModelConfig
	stats    map[string]*ModelStats
	strategy RoutingStrategy
	mu       sync.RWMutex
}

// NewRouter 创建路由器
func NewRouter(strategy RoutingStrategy) *Router {
	return &Router{
		models:   make(map[string]*ModelConfig),
		stats:    make(map[string]*ModelStats),
		strategy: strategy,
	}
}

// RegisterModel 注册模型
func (r *Router) RegisterModel(config *ModelConfig) {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.models[config.Name] = config
	r.stats[config.Name] = &ModelStats{
		LastUpdateTime: time.Now(),
	}
}

// SelectModel 选择模型
func (r *Router) SelectModel(ctx context.Context, req *RoutingRequest) (*ModelConfig, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// 1. 如果指定了模型，直接返回
	if req.PreferredModel != "" {
		if model, ok := r.models[req.PreferredModel]; ok {
			if r.isModelAvailable(req.PreferredModel) {
				return model, nil
			}
		}
	}

	// 2. 根据策略选择模型
	var candidates []*ModelConfig
	for _, model := range r.models {
		// 过滤不可用的模型
		if !r.isModelAvailable(model.Name) {
			continue
		}

		// 根据任务类型过滤
		if req.TaskType != "" && !r.isModelSuitableForTask(model, req.TaskType) {
			continue
		}

		candidates = append(candidates, model)
	}

	if len(candidates) == 0 {
		return nil, errors.New("no available models")
	}

	// 3. 根据策略排序和选择
	switch r.strategy {
	case StrategyCost:
		return r.selectByCost(candidates), nil
	case StrategyPerformance:
		return r.selectByPerformance(candidates), nil
	case StrategyBalanced:
		return r.selectBalanced(candidates, req), nil
	default:
		return candidates[0], nil
	}
}

// selectByCost 按成本选择（成本最低）
func (r *Router) selectByCost(candidates []*ModelConfig) *ModelConfig {
	var selected *ModelConfig
	minCost := math.MaxFloat64

	for _, model := range candidates {
		if model.CostPer1kTokens < minCost {
			minCost = model.CostPer1kTokens
			selected = model
		}
	}

	return selected
}

// selectByPerformance 按性能选择（延迟最低）
func (r *Router) selectByPerformance(candidates []*ModelConfig) *ModelConfig {
	var selected *ModelConfig
	minLatency := math.MaxFloat64

	for _, model := range candidates {
		stats := r.stats[model.Name]
		stats.mu.RLock()
		latency := stats.AvgLatencyMs
		stats.mu.RUnlock()

		if latency == 0 {
			latency = model.AvgResponseTimeMs // 使用配置的默认值
		}

		if latency < minLatency {
			minLatency = latency
			selected = model
		}
	}

	return selected
}

// selectBalanced 平衡选择（综合成本、性能、负载）
func (r *Router) selectBalanced(candidates []*ModelConfig, req *RoutingRequest) *ModelConfig {
	var selected *ModelConfig
	maxScore := -math.MaxFloat64

	for _, model := range candidates {
		score := r.calculateScore(model, req)
		if score > maxScore {
			maxScore = score
			selected = model
		}
	}

	return selected
}

// calculateScore 计算模型得分（越高越好）
func (r *Router) calculateScore(model *ModelConfig, req *RoutingRequest) float64 {
	stats := r.stats[model.Name]
	stats.mu.RLock()
	defer stats.mu.RUnlock()

	// 成本因子（成本越低越好）
	costFactor := 1.0 / (1.0 + model.CostPer1kTokens)

	// 性能因子（延迟越低越好）
	latency := stats.AvgLatencyMs
	if latency == 0 {
		latency = model.AvgResponseTimeMs
	}
	perfFactor := 1.0 / (1.0 + latency/1000.0)

	// 负载因子（负载越低越好）
	loadFactor := 1.0
	if model.MaxConcurrent > 0 {
		loadRatio := float64(stats.CurrentLoad) / float64(model.MaxConcurrent)
		loadFactor = 1.0 - loadRatio
		if loadFactor < 0 {
			loadFactor = 0
		}
	}

	// 成功率因子
	successRate := 1.0
	if stats.TotalRequests > 0 {
		successRate = float64(stats.SuccessRequests) / float64(stats.TotalRequests)
	}

	// 综合得分（可根据需求调整权重）
	score := costFactor*0.3 + perfFactor*0.3 + loadFactor*0.2 + successRate*0.2

	// 考虑优先级
	score *= (1.0 + float64(10-model.Priority)/10.0)

	return score
}

// isModelAvailable 检查模型是否可用
func (r *Router) isModelAvailable(modelName string) bool {
	stats := r.stats[modelName]
	if stats == nil {
		return false
	}

	stats.mu.RLock()
	defer stats.mu.RUnlock()

	model := r.models[modelName]

	// 检查并发限制
	if model.MaxConcurrent > 0 && int(stats.CurrentLoad) >= model.MaxConcurrent {
		return false
	}

	// 检查成功率（如果最近失败率太高，暂时不可用）
	if stats.TotalRequests > 10 {
		successRate := float64(stats.SuccessRequests) / float64(stats.TotalRequests)
		if successRate < 0.5 {
			return false
		}
	}

	return true
}

// isModelSuitableForTask 检查模型是否适合任务
func (r *Router) isModelSuitableForTask(model *ModelConfig, taskType string) bool {
	// 根据任务类型判断模型是否合适
	// 例如：vision任务需要vision模型
	switch taskType {
	case "vision":
		return model.Name == "gpt-4-vision-preview" || model.Name == "claude-3-opus"
	case "embedding":
		return model.Provider == "openai" && model.Name != "gpt-4"
	case "chat", "completion":
		return true
	default:
		return true
	}
}

// UpdateStats 更新统计信息
func (r *Router) UpdateStats(modelName string, success bool, latencyMs float64, tokens int64, cost float64) {
	r.mu.RLock()
	stats := r.stats[modelName]
	r.mu.RUnlock()

	if stats == nil {
		return
	}

	stats.mu.Lock()
	defer stats.mu.Unlock()

	stats.TotalRequests++
	if success {
		stats.SuccessRequests++
	} else {
		stats.FailedRequests++
	}

	stats.TotalTokens += tokens
	stats.TotalCost += cost

	// 更新平均延迟（指数移动平均）
	if stats.AvgLatencyMs == 0 {
		stats.AvgLatencyMs = latencyMs
	} else {
		alpha := 0.1 // 平滑因子
		stats.AvgLatencyMs = alpha*latencyMs + (1-alpha)*stats.AvgLatencyMs
	}

	stats.LastUpdateTime = time.Now()
}

// IncrementLoad 增加负载
func (r *Router) IncrementLoad(modelName string) {
	r.mu.RLock()
	stats := r.stats[modelName]
	r.mu.RUnlock()

	if stats != nil {
		stats.mu.Lock()
		stats.CurrentLoad++
		stats.mu.Unlock()
	}
}

// DecrementLoad 减少负载
func (r *Router) DecrementLoad(modelName string) {
	r.mu.RLock()
	stats := r.stats[modelName]
	r.mu.RUnlock()

	if stats != nil {
		stats.mu.Lock()
		if stats.CurrentLoad > 0 {
			stats.CurrentLoad--
		}
		stats.mu.Unlock()
	}
}

// GetStats 获取统计信息
func (r *Router) GetStats(modelName string) *ModelStats {
	r.mu.RLock()
	defer r.mu.RUnlock()

	stats := r.stats[modelName]
	if stats == nil {
		return nil
	}

	stats.mu.RLock()
	defer stats.mu.RUnlock()

	// 返回副本
	return &ModelStats{
		TotalRequests:   stats.TotalRequests,
		SuccessRequests: stats.SuccessRequests,
		FailedRequests:  stats.FailedRequests,
		TotalTokens:     stats.TotalTokens,
		TotalCost:       stats.TotalCost,
		CurrentLoad:     stats.CurrentLoad,
		AvgLatencyMs:    stats.AvgLatencyMs,
		LastUpdateTime:  stats.LastUpdateTime,
	}
}

// GetAllStats 获取所有统计
func (r *Router) GetAllStats() map[string]*ModelStats {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make(map[string]*ModelStats)
	for name := range r.stats {
		result[name] = r.GetStats(name)
	}
	return result
}

// RoutingRequest 路由请求
type RoutingRequest struct {
	PreferredModel  string          // 优先模型
	TaskType        string          // 任务类型
	EstimatedTokens int             // 预估token数
	MaxBudget       float64         // 最大预算
	Context         context.Context // 请求上下文
}

// RoutingResponse 路由响应
type RoutingResponse struct {
	SelectedModel *ModelConfig
	Reason        string
	EstimatedCost float64
}

// String 格式化输出
func (m *ModelConfig) String() string {
	return fmt.Sprintf("Model{name=%s, provider=%s, cost=%.4f}", m.Name, m.Provider, m.CostPer1kTokens)
}
