package domain

import (
	"time"

	"github.com/google/uuid"
)

// RoutingStrategy 路由策略
type RoutingStrategy string

const (
	StrategyPriority     RoutingStrategy = "priority"      // 优先级路由
	StrategyRoundRobin   RoutingStrategy = "round_robin"   // 轮询
	StrategyWeighted     RoutingStrategy = "weighted"      // 加权轮询
	StrategyLeastLatency RoutingStrategy = "least_latency" // 最低延迟
	StrategyLeastCost    RoutingStrategy = "least_cost"    // 最低成本
	StrategyRandom       RoutingStrategy = "random"        // 随机
)

// RouteRequest 路由请求
type RouteRequest struct {
	ID                   string
	ModelType            ModelType
	RequiredCapabilities []string
	MaxTokens            int
	PreferredProvider    ModelProvider
	Strategy             RoutingStrategy
	Context              map[string]interface{}
	CreatedAt            time.Time
}

// NewRouteRequest 创建路由请求
func NewRouteRequest(
	modelType ModelType,
	strategy RoutingStrategy,
) *RouteRequest {
	return &RouteRequest{
		ID:                   "req_" + uuid.New().String(),
		ModelType:            modelType,
		Strategy:             strategy,
		RequiredCapabilities: make([]string, 0),
		Context:              make(map[string]interface{}),
		CreatedAt:            time.Now(),
	}
}

// RouteResult 路由结果
type RouteResult struct {
	RequestID         string
	SelectedModel     *Model
	AlternativeModels []*Model
	Strategy          RoutingStrategy
	Reason            string
	RoutedAt          time.Time
}

// NewRouteResult 创建路由结果
func NewRouteResult(
	requestID string,
	model *Model,
	strategy RoutingStrategy,
	reason string,
) *RouteResult {
	return &RouteResult{
		RequestID:         requestID,
		SelectedModel:     model,
		AlternativeModels: make([]*Model, 0),
		Strategy:          strategy,
		Reason:            reason,
		RoutedAt:          time.Now(),
	}
}

// ModelMetrics 模型指标
type ModelMetrics struct {
	ModelID         string
	TotalRequests   int64
	SuccessRequests int64
	FailedRequests  int64
	AvgLatencyMs    float64
	P95LatencyMs    float64
	P99LatencyMs    float64
	TotalTokens     int64
	TotalCost       float64
	ErrorRate       float64
	LastRequestAt   *time.Time
	UpdatedAt       time.Time
}

// NewModelMetrics 创建模型指标
func NewModelMetrics(modelID string) *ModelMetrics {
	return &ModelMetrics{
		ModelID:   modelID,
		UpdatedAt: time.Now(),
	}
}

// RecordRequest 记录请求
func (m *ModelMetrics) RecordRequest(success bool, latencyMs int, tokens int, cost float64) {
	m.TotalRequests++
	if success {
		m.SuccessRequests++
	} else {
		m.FailedRequests++
	}

	// 更新平均延迟（简化计算）
	if m.AvgLatencyMs == 0 {
		m.AvgLatencyMs = float64(latencyMs)
	} else {
		m.AvgLatencyMs = (m.AvgLatencyMs*float64(m.TotalRequests-1) + float64(latencyMs)) / float64(m.TotalRequests)
	}

	m.TotalTokens += int64(tokens)
	m.TotalCost += cost

	// 计算错误率
	if m.TotalRequests > 0 {
		m.ErrorRate = float64(m.FailedRequests) / float64(m.TotalRequests)
	}

	now := time.Now()
	m.LastRequestAt = &now
	m.UpdatedAt = now
}

// IsHealthy 检查健康状态
func (m *ModelMetrics) IsHealthy() bool {
	// 错误率 < 10%
	return m.ErrorRate < 0.1
}

// GetScore 获取评分（用于路由决策）
func (m *ModelMetrics) GetScore() float64 {
	// 综合评分：考虑成功率和延迟
	successRate := 1.0 - m.ErrorRate
	latencyScore := 1.0 / (1.0 + m.AvgLatencyMs/1000.0) // 延迟越低分数越高

	return successRate*0.7 + latencyScore*0.3
}
