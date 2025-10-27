package biz

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"sync"
	"time"
)

// RoutingStrategy 路由策略
type RoutingStrategy string

const (
	StrategyRoundRobin       RoutingStrategy = "round_robin"
	StrategyWeightedRR       RoutingStrategy = "weighted_round_robin"
	StrategyLeastConnections RoutingStrategy = "least_connections"
	StrategyCostOptimized    RoutingStrategy = "cost_optimized"
	StrategyPerformance      RoutingStrategy = "performance"
	StrategyBalanced         RoutingStrategy = "balanced"
)

// ModelBackend 模型后端
type ModelBackend struct {
	ID           string
	ModelName    string
	Provider     string // openai, anthropic, azure, etc.
	Endpoint     string
	APIKey       string
	Weight       int     // 权重（1-100）
	MaxQPS       int     // 最大QPS
	CostPerToken float64 // 每token成本

	// 运行时状态
	CurrentConnections int32
	HealthStatus       string
	AvgLatencyMs       float64
	ErrorRate          float64
	LastHealthCheck    time.Time
}

// RoutingRequest 路由请求
type RoutingRequest struct {
	TenantID   string
	UserID     string
	ModelName  string
	Strategy   RoutingStrategy
	MaxLatency int // 最大延迟（ms）
	MaxCost    float64
	Priority   int // 优先级（1-10）
}

// RoutingResult 路由结果
type RoutingResult struct {
	Backend     *ModelBackend
	RoutingTime time.Duration
	Reason      string
}

// SmartRoutingUsecase 智能路由用例
type SmartRoutingUsecase struct {
	backends         map[string][]*ModelBackend // modelName -> backends
	backendsMu       sync.RWMutex
	roundRobinIndex  map[string]int
	rrMu             sync.Mutex
	healthChecker    *HealthChecker
	metricsCollector MetricsCollector
}

// NewSmartRoutingUsecase 创建智能路由用例
func NewSmartRoutingUsecase(
	metricsCollector MetricsCollector,
) *SmartRoutingUsecase {
	uc := &SmartRoutingUsecase{
		backends:         make(map[string][]*ModelBackend),
		roundRobinIndex:  make(map[string]int),
		metricsCollector: metricsCollector,
	}

	// 启动健康检查
	uc.healthChecker = NewHealthChecker(uc)
	go uc.healthChecker.Start()

	return uc
}

// RegisterBackend 注册模型后端
func (uc *SmartRoutingUsecase) RegisterBackend(backend *ModelBackend) error {
	uc.backendsMu.Lock()
	defer uc.backendsMu.Unlock()

	if uc.backends[backend.ModelName] == nil {
		uc.backends[backend.ModelName] = make([]*ModelBackend, 0)
	}

	uc.backends[backend.ModelName] = append(uc.backends[backend.ModelName], backend)

	return nil
}

// Route 智能路由
func (uc *SmartRoutingUsecase) Route(
	ctx context.Context,
	req *RoutingRequest,
) (*RoutingResult, error) {
	startTime := time.Now()

	// 1. 获取可用后端
	backends := uc.getAvailableBackends(req.ModelName)
	if len(backends) == 0 {
		return nil, errors.New("no available backends")
	}

	// 2. 根据策略选择后端
	var backend *ModelBackend
	var reason string
	var err error

	switch req.Strategy {
	case StrategyRoundRobin:
		backend, reason = uc.routeRoundRobin(backends, req.ModelName)
	case StrategyWeightedRR:
		backend, reason = uc.routeWeightedRoundRobin(backends, req.ModelName)
	case StrategyLeastConnections:
		backend, reason = uc.routeLeastConnections(backends)
	case StrategyCostOptimized:
		backend, reason, err = uc.routeCostOptimized(backends, req)
	case StrategyPerformance:
		backend, reason, err = uc.routePerformance(backends, req)
	case StrategyBalanced:
		backend, reason, err = uc.routeBalanced(backends, req)
	default:
		backend, reason = uc.routeRoundRobin(backends, req.ModelName)
	}

	if err != nil {
		return nil, err
	}

	if backend == nil {
		return nil, errors.New("failed to select backend")
	}

	// 3. 记录路由结果
	uc.metricsCollector.RecordRouting(backend.ID, req.ModelName, string(req.Strategy))

	return &RoutingResult{
		Backend:     backend,
		RoutingTime: time.Since(startTime),
		Reason:      reason,
	}, nil
}

// getAvailableBackends 获取可用后端
func (uc *SmartRoutingUsecase) getAvailableBackends(modelName string) []*ModelBackend {
	uc.backendsMu.RLock()
	defer uc.backendsMu.RUnlock()

	backends := uc.backends[modelName]
	available := make([]*ModelBackend, 0)

	for _, backend := range backends {
		// 只返回健康的后端
		if backend.HealthStatus == "healthy" {
			available = append(available, backend)
		}
	}

	return available
}

// routeRoundRobin 轮询路由
func (uc *SmartRoutingUsecase) routeRoundRobin(
	backends []*ModelBackend,
	modelName string,
) (*ModelBackend, string) {
	uc.rrMu.Lock()
	defer uc.rrMu.Unlock()

	index := uc.roundRobinIndex[modelName]
	backend := backends[index]

	// 更新索引
	uc.roundRobinIndex[modelName] = (index + 1) % len(backends)

	return backend, "round_robin"
}

// routeWeightedRoundRobin 加权轮询路由
func (uc *SmartRoutingUsecase) routeWeightedRoundRobin(
	backends []*ModelBackend,
	modelName string,
) (*ModelBackend, string) {
	// 计算总权重
	totalWeight := 0
	for _, b := range backends {
		totalWeight += b.Weight
	}

	// 随机选择
	randWeight := rand.Intn(totalWeight)
	currentWeight := 0

	for _, backend := range backends {
		currentWeight += backend.Weight
		if randWeight < currentWeight {
			return backend, "weighted_round_robin"
		}
	}

	return backends[0], "weighted_round_robin"
}

// routeLeastConnections 最少连接路由
func (uc *SmartRoutingUsecase) routeLeastConnections(
	backends []*ModelBackend,
) (*ModelBackend, string) {
	var selected *ModelBackend
	minConnections := int32(999999)

	for _, backend := range backends {
		if backend.CurrentConnections < minConnections {
			minConnections = backend.CurrentConnections
			selected = backend
		}
	}

	return selected, "least_connections"
}

// routeCostOptimized 成本优化路由
func (uc *SmartRoutingUsecase) routeCostOptimized(
	backends []*ModelBackend,
	req *RoutingRequest,
) (*ModelBackend, string, error) {
	// 选择成本最低的后端
	var selected *ModelBackend
	minCost := float64(999999)

	for _, backend := range backends {
		// 检查是否超过成本限制
		if req.MaxCost > 0 && backend.CostPerToken > req.MaxCost {
			continue
		}

		// 综合考虑成本和健康状态
		adjustedCost := backend.CostPerToken
		if backend.ErrorRate > 0.05 { // 错误率超过5%，提高成本权重
			adjustedCost *= (1 + backend.ErrorRate*10)
		}

		if adjustedCost < minCost {
			minCost = adjustedCost
			selected = backend
		}
	}

	if selected == nil {
		return nil, "", errors.New("no backend within cost limit")
	}

	return selected, fmt.Sprintf("cost_optimized(cost=%.6f)", selected.CostPerToken), nil
}

// routePerformance 性能优化路由
func (uc *SmartRoutingUsecase) routePerformance(
	backends []*ModelBackend,
	req *RoutingRequest,
) (*ModelBackend, string, error) {
	// 选择延迟最低的后端
	var selected *ModelBackend
	minLatency := float64(999999)

	for _, backend := range backends {
		// 检查是否超过延迟限制
		if req.MaxLatency > 0 && backend.AvgLatencyMs > float64(req.MaxLatency) {
			continue
		}

		// 综合考虑延迟和连接数
		adjustedLatency := backend.AvgLatencyMs * (1 + float64(backend.CurrentConnections)*0.1)

		if adjustedLatency < minLatency {
			minLatency = adjustedLatency
			selected = backend
		}
	}

	if selected == nil {
		return nil, "", errors.New("no backend within latency limit")
	}

	return selected, fmt.Sprintf("performance(latency=%.2fms)", selected.AvgLatencyMs), nil
}

// routeBalanced 平衡路由（综合成本和性能）
func (uc *SmartRoutingUsecase) routeBalanced(
	backends []*ModelBackend,
	req *RoutingRequest,
) (*ModelBackend, string, error) {
	var selected *ModelBackend
	bestScore := float64(-1)

	for _, backend := range backends {
		// 计算综合分数（越低越好）
		// 归一化延迟（假设最大1000ms）
		latencyScore := backend.AvgLatencyMs / 1000.0

		// 归一化成本（假设最大$0.01/token）
		costScore := backend.CostPerToken / 0.01

		// 连接数分数
		connectionScore := float64(backend.CurrentConnections) / 100.0

		// 错误率分数
		errorScore := backend.ErrorRate * 10

		// 综合分数（权重可调整）
		score := latencyScore*0.3 + costScore*0.3 + connectionScore*0.2 + errorScore*0.2

		// 越低越好，但要反转才能找到最高分
		if bestScore < 0 || score < bestScore {
			bestScore = score
			selected = backend
		}
	}

	if selected == nil {
		return backends[0], "balanced(fallback)", nil
	}

	return selected, fmt.Sprintf("balanced(score=%.2f)", bestScore), nil
}

// HealthChecker 健康检查器
type HealthChecker struct {
	uc       *SmartRoutingUsecase
	interval time.Duration
}

// NewHealthChecker 创建健康检查器
func NewHealthChecker(uc *SmartRoutingUsecase) *HealthChecker {
	return &HealthChecker{
		uc:       uc,
		interval: 30 * time.Second,
	}
}

// Start 启动健康检查
func (hc *HealthChecker) Start() {
	ticker := time.NewTicker(hc.interval)
	defer ticker.Stop()

	for range ticker.C {
		hc.checkAll()
	}
}

// checkAll 检查所有后端
func (hc *HealthChecker) checkAll() {
	hc.uc.backendsMu.RLock()
	defer hc.uc.backendsMu.RUnlock()

	for _, backends := range hc.uc.backends {
		for _, backend := range backends {
			go hc.checkBackend(backend)
		}
	}
}

// checkBackend 检查单个后端
func (hc *HealthChecker) checkBackend(backend *ModelBackend) {
	// 简化的健康检查（实际应该调用backend的健康检查接口）
	// 这里只更新时间戳
	backend.LastHealthCheck = time.Now()

	// 模拟健康状态更新
	if backend.ErrorRate < 0.1 {
		backend.HealthStatus = "healthy"
	} else if backend.ErrorRate < 0.3 {
		backend.HealthStatus = "degraded"
	} else {
		backend.HealthStatus = "unhealthy"
	}
}

// MetricsCollector 指标收集器接口
type MetricsCollector interface {
	RecordRouting(backendID, modelName, strategy string)
	RecordLatency(backendID string, latency float64)
	RecordError(backendID string)
}
