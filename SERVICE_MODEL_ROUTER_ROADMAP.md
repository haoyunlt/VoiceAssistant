# Model Router 服务功能清单与迭代计划

## 服务概述

Model Router 是智能模型路由服务，负责模型选择、负载均衡、成本优化和降级策略。

**技术栈**: Go + Kratos + Redis + PostgreSQL

**端口**: 9004

---

## 一、功能完成度评估

### ✅ 已完成功能

#### 1. 基础框架

- ✅ Kratos 框架搭建
- ✅ 配置管理
- ✅ 日志系统

#### 2. 部分功能

- ✅ A/B 测试框架（部分）
- ✅ 健康检查框架（部分）
- ✅ 成本优化器框架（部分）

---

## 二、待完成功能清单

### 🔄 P0 - 核心功能（迭代 1：2 周）

#### 1. 路由逻辑实现

**当前状态**: 占位代码

**位置**: `cmd/model-router/main.go`

**待实现**:

```go
// 文件: cmd/model-router/internal/application/router_service.go

package application

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

type RouterService struct {
	modelRepo    *data.ModelRepository
	strategyRepo *data.StrategyRepository
	redis        *redis.Client
}

// RouteRequest 路由请求到最优模型
func (s *RouterService) RouteRequest(ctx context.Context, req *RouteRequest) (*RouteResponse, error) {
	// 1. 解析策略
	strategy := s.determineStrategy(req)

	// 2. 获取候选模型
	candidates, err := s.getCandidateModels(ctx, req)
	if err != nil {
		return nil, err
	}

	// 3. 根据策略选择模型
	selectedModel, err := s.selectModel(ctx, candidates, strategy, req)
	if err != nil {
		return nil, err
	}

	// 4. 检查健康状态
	if !s.isModelHealthy(ctx, selectedModel.ID) {
		// 降级到备用模型
		selectedModel, err = s.getFallbackModel(ctx, selectedModel)
		if err != nil {
			return nil, err
		}
	}

	// 5. 记录路由决策
	s.recordRouting(ctx, req, selectedModel)

	return &RouteResponse{
		ModelID:      selectedModel.ID,
		ModelName:    selectedModel.Name,
		Provider:     selectedModel.Provider,
		Endpoint:     selectedModel.Endpoint,
		EstimatedCost: s.estimateCost(selectedModel, req),
		Strategy:     strategy,
	}, nil
}

// determineStrategy 确定路由策略
func (s *RouterService) determineStrategy(req *RouteRequest) RoutingStrategy {
	// 优先使用用户指定的策略
	if req.Strategy != "" {
		return RoutingStrategy(req.Strategy)
	}

	// 根据请求类型选择策略
	switch {
	case req.MaxTokens > 4000:
		// 长文本，优先性能
		return StrategyPerformance
	case req.Temperature < 0.3:
		// 确定性任务，优先成本
		return StrategyCost
	default:
		// 平衡模式
		return StrategyBalanced
	}
}

// getCandidateModels 获取候选模型
func (s *RouterService) getCandidateModels(ctx context.Context, req *RouteRequest) ([]*Model, error) {
	filters := &ModelFilters{
		TaskType:     req.TaskType,
		MinTokens:    req.MaxTokens,
		SupportedLangs: req.Language,
		Available:    true,
	}

	return s.modelRepo.ListModels(ctx, filters)
}

// selectModel 根据策略选择模型
func (s *RouterService) selectModel(
	ctx context.Context,
	candidates []*Model,
	strategy RoutingStrategy,
	req *RouteRequest,
) (*Model, error) {
	if len(candidates) == 0 {
		return nil, fmt.Errorf("no candidate models found")
	}

	switch strategy {
	case StrategyCost:
		return s.selectByCost(candidates, req)
	case StrategyPerformance:
		return s.selectByPerformance(candidates, req)
	case StrategyBalanced:
		return s.selectBalanced(candidates, req)
	case StrategyLoadBalance:
		return s.selectByLoadBalance(ctx, candidates)
	default:
		return candidates[0], nil
	}
}

// selectByCost 按成本选择
func (s *RouterService) selectByCost(candidates []*Model, req *RouteRequest) (*Model, error) {
	minCost := float64(999999)
	var selected *Model

	for _, model := range candidates {
		cost := s.estimateCost(model, req)
		if cost < minCost {
			minCost = cost
			selected = model
		}
	}

	return selected, nil
}

// selectByPerformance 按性能选择
func (s *RouterService) selectByPerformance(candidates []*Model, req *RouteRequest) (*Model, error) {
	maxScore := float64(0)
	var selected *Model

	for _, model := range candidates {
		// 性能分数 = 质量分 * 0.6 + 速度分 * 0.4
		score := model.QualityScore*0.6 + (1.0/model.AvgLatencyMs)*1000*0.4

		if score > maxScore {
			maxScore = score
			selected = model
		}
	}

	return selected, nil
}

// selectBalanced 平衡选择
func (s *RouterService) selectBalanced(candidates []*Model, req *RouteRequest) (*Model, error) {
	maxScore := float64(0)
	var selected *Model

	for _, model := range candidates {
		// 平衡分数 = 质量 * 0.4 + 速度 * 0.3 + (1/成本) * 0.3
		estimatedCost := s.estimateCost(model, req)

		qualityScore := model.QualityScore * 0.4
		speedScore := (1.0 / model.AvgLatencyMs) * 1000 * 0.3
		costScore := (1.0 / estimatedCost) * 0.3

		score := qualityScore + speedScore + costScore

		if score > maxScore {
			maxScore = score
			selected = model
		}
	}

	return selected, nil
}

// selectByLoadBalance 负载均衡选择
func (s *RouterService) selectByLoadBalance(ctx context.Context, candidates []*Model) (*Model, error) {
	// 加权轮询
	return s.weightedRoundRobin(ctx, candidates)
}

// weightedRoundRobin 加权轮询
func (s *RouterService) weightedRoundRobin(ctx context.Context, candidates []*Model) (*Model, error) {
	// 获取每个模型的当前负载
	loads := make(map[string]int64)
	for _, model := range candidates {
		key := fmt.Sprintf("model:load:%s", model.ID)
		load, _ := s.redis.Get(ctx, key).Int64()
		loads[model.ID] = load
	}

	// 计算加权分数（权重越高越优先，负载越低越优先）
	maxScore := float64(-1)
	var selected *Model

	for _, model := range candidates {
		load := loads[model.ID]
		// 分数 = 权重 / (负载 + 1)
		score := float64(model.Weight) / float64(load+1)

		if score > maxScore {
			maxScore = score
			selected = model
		}
	}

	// 增加选中模型的负载计数
	if selected != nil {
		key := fmt.Sprintf("model:load:%s", selected.ID)
		s.redis.Incr(ctx, key)
		s.redis.Expire(ctx, key, 5*time.Minute)
	}

	return selected, nil
}

// estimateCost 估算成本
func (s *RouterService) estimateCost(model *Model, req *RouteRequest) float64 {
	// 估算 token 数量
	estimatedTokens := float64(req.MaxTokens)
	if req.Prompt != "" {
		estimatedTokens += float64(len(req.Prompt)) / 4.0 // 粗略估算
	}

	// 计算成本
	return (estimatedTokens / 1000.0) * model.CostPer1KTokens
}

// isModelHealthy 检查模型健康状态
func (s *RouterService) isModelHealthy(ctx context.Context, modelID string) bool {
	key := fmt.Sprintf("model:health:%s", modelID)

	// 从 Redis 获取健康状态
	status, err := s.redis.Get(ctx, key).Result()
	if err != nil || status != "healthy" {
		return false
	}

	return true
}

// getFallbackModel 获取备用模型
func (s *RouterService) getFallbackModel(ctx context.Context, primary *Model) (*Model, error) {
	// 获取同类型的其他模型
	candidates, err := s.modelRepo.ListModels(ctx, &ModelFilters{
		TaskType:  primary.TaskType,
		Available: true,
	})
	if err != nil {
		return nil, err
	}

	// 排除主模型
	fallbacks := make([]*Model, 0)
	for _, m := range candidates {
		if m.ID != primary.ID && s.isModelHealthy(ctx, m.ID) {
			fallbacks = append(fallbacks, m)
		}
	}

	if len(fallbacks) == 0 {
		return nil, fmt.Errorf("no fallback model available")
	}

	// 选择成本最低的备用模型
	return s.selectByCost(fallbacks, &RouteRequest{
		MaxTokens: 1000,
	})
}

// recordRouting 记录路由决策
func (s *RouterService) recordRouting(ctx context.Context, req *RouteRequest, model *Model) {
	// 记录到数据库用于分析
	record := &RoutingRecord{
		ModelID:      model.ID,
		Strategy:     string(req.Strategy),
		RequestType:  req.TaskType,
		EstimatedCost: s.estimateCost(model, req),
		Timestamp:    time.Now(),
	}

	s.modelRepo.SaveRoutingRecord(ctx, record)

	// 更新模型使用统计
	key := fmt.Sprintf("model:usage:%s", model.ID)
	s.redis.Incr(ctx, key)
}
```

**验收标准**:

- [ ] 支持 4 种路由策略
- [ ] 成本估算准确
- [ ] 健康检查正常
- [ ] 降级机制有效

#### 2. 模型注册表实现

**当前状态**: 部分实现

**位置**: `cmd/model-router/internal/domain/model_registry.go`

**待实现**:

```go
// 文件: cmd/model-router/internal/data/model_repo.go

package data

type ModelRepository struct {
	db    *gorm.DB
	cache *redis.Client
}

// RegisterModel 注册新模型
func (r *ModelRepository) RegisterModel(ctx context.Context, model *Model) error {
	// 验证模型配置
	if err := r.validateModel(model); err != nil {
		return err
	}

	// 保存到数据库
	if err := r.db.WithContext(ctx).Create(model).Error; err != nil {
		return err
	}

	// 清除缓存
	r.invalidateCache(ctx)

	// 初始化健康状态
	r.initializeHealth(ctx, model.ID)

	return nil
}

// UpdateModel 更新模型
func (r *ModelRepository) UpdateModel(ctx context.Context, model *Model) error {
	if err := r.db.WithContext(ctx).Save(model).Error; err != nil {
		return err
	}

	r.invalidateCache(ctx)
	return nil
}

// GetModel 获取模型
func (r *ModelRepository) GetModel(ctx context.Context, modelID string) (*Model, error) {
	// 先查缓存
	cacheKey := fmt.Sprintf("model:%s", modelID)
	cached, err := r.cache.Get(ctx, cacheKey).Result()
	if err == nil {
		var model Model
		if err := json.Unmarshal([]byte(cached), &model); err == nil {
			return &model, nil
		}
	}

	// 查数据库
	var model Model
	if err := r.db.WithContext(ctx).Where("id = ?", modelID).First(&model).Error; err != nil {
		return nil, err
	}

	// 写入缓存
	data, _ := json.Marshal(model)
	r.cache.Set(ctx, cacheKey, data, 10*time.Minute)

	return &model, nil
}

// ListModels 列出模型
func (r *ModelRepository) ListModels(ctx context.Context, filters *ModelFilters) ([]*Model, error) {
	// 构建查询
	query := r.db.WithContext(ctx).Model(&Model{})

	if filters.TaskType != "" {
		query = query.Where("task_type = ?", filters.TaskType)
	}

	if filters.Provider != "" {
		query = query.Where("provider = ?", filters.Provider)
	}

	if filters.Available {
		query = query.Where("available = ?", true)
	}

	if filters.MinTokens > 0 {
		query = query.Where("max_tokens >= ?", filters.MinTokens)
	}

	// 执行查询
	var models []*Model
	if err := query.Find(&models).Error; err != nil {
		return nil, err
	}

	return models, nil
}

// UpdateModelStats 更新模型统计
func (r *ModelRepository) UpdateModelStats(ctx context.Context, modelID string, stats *ModelStats) error {
	updates := map[string]interface{}{
		"total_requests":   gorm.Expr("total_requests + ?", stats.RequestCount),
		"total_tokens":     gorm.Expr("total_tokens + ?", stats.TokenCount),
		"total_cost":       gorm.Expr("total_cost + ?", stats.Cost),
		"avg_latency_ms":   stats.AvgLatency,
		"error_count":      gorm.Expr("error_count + ?", stats.ErrorCount),
		"last_used_at":     time.Now(),
	}

	return r.db.WithContext(ctx).
		Model(&Model{}).
		Where("id = ?", modelID).
		Updates(updates).Error
}

// GetModelStats 获取模型统计
func (r *ModelRepository) GetModelStats(ctx context.Context, modelID string, startTime, endTime time.Time) (*ModelStatsDetail, error) {
	var stats ModelStatsDetail

	err := r.db.WithContext(ctx).
		Table("routing_records").
		Select(`
			COUNT(*) as total_requests,
			SUM(estimated_cost) as total_cost,
			AVG(actual_latency_ms) as avg_latency,
			SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
		`).
		Where("model_id = ? AND timestamp BETWEEN ? AND ?", modelID, startTime, endTime).
		Scan(&stats).Error

	return &stats, err
}

func (r *ModelRepository) validateModel(model *Model) error {
	if model.Name == "" {
		return fmt.Errorf("model name is required")
	}

	if model.Provider == "" {
		return fmt.Errorf("provider is required")
	}

	if model.Endpoint == "" {
		return fmt.Errorf("endpoint is required")
	}

	if model.MaxTokens <= 0 {
		return fmt.Errorf("max_tokens must be positive")
	}

	return nil
}

func (r *ModelRepository) invalidateCache(ctx context.Context) {
	// 删除模型列表缓存
	keys, _ := r.cache.Keys(ctx, "model:*").Result()
	if len(keys) > 0 {
		r.cache.Del(ctx, keys...)
	}
}

func (r *ModelRepository) initializeHealth(ctx context.Context, modelID string) {
	key := fmt.Sprintf("model:health:%s", modelID)
	r.cache.Set(ctx, key, "healthy", 5*time.Minute)
}
```

**验收标准**:

- [ ] 模型注册完成
- [ ] 模型查询优化
- [ ] 统计功能完整
- [ ] 缓存机制有效

#### 3. 健康检查完善

**当前状态**: 基础框架

**位置**: `cmd/model-router/internal/application/health_checker.go`

**待实现**:

```go
// 文件: cmd/model-router/internal/application/health_checker.go

package application

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"
)

type HealthChecker struct {
	modelRepo    *data.ModelRepository
	redis        *redis.Client
	httpClient   *http.Client
	checkInterval time.Duration
	mu           sync.RWMutex
	stopChan     chan struct{}
}

func NewHealthChecker(modelRepo *data.ModelRepository, redis *redis.Client) *HealthChecker {
	return &HealthChecker{
		modelRepo:     modelRepo,
		redis:         redis,
		httpClient:    &http.Client{Timeout: 10 * time.Second},
		checkInterval: 30 * time.Second,
		stopChan:      make(chan struct{}),
	}
}

// Start 启动健康检查
func (hc *HealthChecker) Start(ctx context.Context) {
	ticker := time.NewTicker(hc.checkInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			hc.checkAllModels(ctx)
		case <-hc.stopChan:
			return
		case <-ctx.Done():
			return
		}
	}
}

// Stop 停止健康检查
func (hc *HealthChecker) Stop() {
	close(hc.stopChan)
}

// checkAllModels 检查所有模型
func (hc *HealthChecker) checkAllModels(ctx context.Context) {
	models, err := hc.modelRepo.ListModels(ctx, &ModelFilters{
		Available: true,
	})
	if err != nil {
		logger.Error("Failed to list models", "error", err)
		return
	}

	// 并发检查
	var wg sync.WaitGroup
	for _, model := range models {
		wg.Add(1)
		go func(m *Model) {
			defer wg.Done()
			hc.checkModel(ctx, m)
		}(model)
	}

	wg.Wait()
}

// checkModel 检查单个模型
func (hc *HealthChecker) checkModel(ctx context.Context, model *Model) {
	start := time.Now()

	// 执行健康检查
	healthy, latency, err := hc.performHealthCheck(ctx, model)

	// 更新状态
	status := "healthy"
	if !healthy {
		status = "unhealthy"
		logger.Warn("Model unhealthy",
			"model_id", model.ID,
			"model_name", model.Name,
			"error", err,
		)
	}

	// 保存到 Redis
	key := fmt.Sprintf("model:health:%s", model.ID)
	hc.redis.Set(ctx, key, status, 5*time.Minute)

	// 更新延迟统计
	if healthy {
		hc.updateLatencyStats(ctx, model.ID, latency)
	}

	// 记录检查结果
	hc.recordHealthCheck(ctx, &HealthCheckRecord{
		ModelID:   model.ID,
		Status:    status,
		Latency:   latency,
		Error:     errToString(err),
		Timestamp: time.Now(),
		Duration:  time.Since(start),
	})
}

// performHealthCheck 执行健康检查
func (hc *HealthChecker) performHealthCheck(ctx context.Context, model *Model) (bool, time.Duration, error) {
	switch model.Provider {
	case "openai":
		return hc.checkOpenAI(ctx, model)
	case "anthropic":
		return hc.checkAnthropic(ctx, model)
	case "zhipu":
		return hc.checkZhipu(ctx, model)
	case "qwen":
		return hc.checkQwen(ctx, model)
	case "baidu":
		return hc.checkBaidu(ctx, model)
	default:
		return hc.checkGeneric(ctx, model)
	}
}

// checkOpenAI 检查 OpenAI 模型
func (hc *HealthChecker) checkOpenAI(ctx context.Context, model *Model) (bool, time.Duration, error) {
	start := time.Now()

	// 发送测试请求
	req, err := http.NewRequestWithContext(ctx, "POST", model.Endpoint,
		strings.NewReader(`{
			"model": "`+model.Name+`",
			"messages": [{"role":"user","content":"test"}],
			"max_tokens": 5
		}`))
	if err != nil {
		return false, 0, err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+model.APIKey)

	resp, err := hc.httpClient.Do(req)
	latency := time.Since(start)

	if err != nil {
		return false, latency, err
	}
	defer resp.Body.Close()

	// 检查响应
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return true, latency, nil
	}

	body, _ := io.ReadAll(resp.Body)
	return false, latency, fmt.Errorf("status: %d, body: %s", resp.StatusCode, string(body))
}

// checkGeneric 通用健康检查
func (hc *HealthChecker) checkGeneric(ctx context.Context, model *Model) (bool, time.Duration, error) {
	start := time.Now()

	// 简单的 HTTP GET 请求
	req, err := http.NewRequestWithContext(ctx, "GET", model.Endpoint, nil)
	if err != nil {
		return false, 0, err
	}

	resp, err := hc.httpClient.Do(req)
	latency := time.Since(start)

	if err != nil {
		return false, latency, err
	}
	defer resp.Body.Close()

	return resp.StatusCode < 500, latency, nil
}

// updateLatencyStats 更新延迟统计
func (hc *HealthChecker) updateLatencyStats(ctx context.Context, modelID string, latency time.Duration) {
	// 使用 Redis 保存最近的延迟数据
	key := fmt.Sprintf("model:latency:%s", modelID)

	// 添加到 sorted set（时间戳作为分数）
	hc.redis.ZAdd(ctx, key, &redis.Z{
		Score:  float64(time.Now().Unix()),
		Member: latency.Milliseconds(),
	})

	// 保留最近 1 小时的数据
	oneHourAgo := time.Now().Add(-time.Hour).Unix()
	hc.redis.ZRemRangeByScore(ctx, key, "0", fmt.Sprintf("%d", oneHourAgo))
}

// GetModelHealth 获取模型健康状态
func (hc *HealthChecker) GetModelHealth(ctx context.Context, modelID string) (*ModelHealth, error) {
	// 获取健康状态
	statusKey := fmt.Sprintf("model:health:%s", modelID)
	status, err := hc.redis.Get(ctx, statusKey).Result()
	if err != nil {
		status = "unknown"
	}

	// 获取延迟统计
	latencyKey := fmt.Sprintf("model:latency:%s", modelID)
	latencies, err := hc.redis.ZRange(ctx, latencyKey, 0, -1).Result()

	avgLatency := float64(0)
	if len(latencies) > 0 {
		total := float64(0)
		for _, l := range latencies {
			if val, err := strconv.ParseFloat(l, 64); err == nil {
				total += val
			}
		}
		avgLatency = total / float64(len(latencies))
	}

	return &ModelHealth{
		ModelID:      modelID,
		Status:       status,
		AvgLatencyMs: avgLatency,
		CheckCount:   len(latencies),
		LastCheck:    time.Now(),
	}, nil
}

func (hc *HealthChecker) recordHealthCheck(ctx context.Context, record *HealthCheckRecord) {
	// 保存到数据库用于历史分析
	hc.modelRepo.SaveHealthCheckRecord(ctx, record)
}

func errToString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
```

**验收标准**:

- [ ] 定时健康检查
- [ ] 多提供商支持
- [ ] 延迟统计准确
- [ ] 自动标记不健康模型

---

### 🔄 P1 - 高级功能（迭代 2：1 周）

#### 1. A/B 测试完善

```go
// 文件: cmd/model-router/internal/application/ab_testing_service.go

// CreateExperiment 创建实验
func (s *ABTestingService) CreateExperiment(ctx context.Context, exp *Experiment) error {
	// 验证实验配置
	if err := s.validateExperiment(exp); err != nil {
		return err
	}

	// 保存实验
	if err := s.repo.SaveExperiment(ctx, exp); err != nil {
		return err
	}

	// 初始化实验状态
	s.initializeExperiment(ctx, exp)

	return nil
}

// RouteWithExperiment 带实验的路由
func (s *ABTestingService) RouteWithExperiment(
	ctx context.Context,
	userID string,
	req *RouteRequest,
) (*RouteResponse, error) {
	// 获取活跃实验
	experiments, err := s.repo.GetActiveExperiments(ctx)
	if err != nil {
		return nil, err
	}

	// 检查用户是否在实验中
	for _, exp := range experiments {
		if s.isUserInExperiment(ctx, userID, exp) {
			// 分配变体
			variant := s.assignVariant(ctx, userID, exp)

			// 使用变体的模型
			req.ModelID = variant.ModelID

			// 记录分配
			s.recordAssignment(ctx, userID, exp.ID, variant.ID)

			break
		}
	}

	// 执行路由
	return s.routerService.RouteRequest(ctx, req)
}

// RecordMetric 记录指标
func (s *ABTestingService) RecordMetric(ctx context.Context, metric *ExperimentMetric) error {
	// 保存指标
	if err := s.repo.SaveMetric(ctx, metric); err != nil {
		return err
	}

	// 更新实验统计
	s.updateExperimentStats(ctx, metric)

	// 检查是否需要早停
	if s.shouldEarlyStop(ctx, metric.ExperimentID) {
		s.stopExperiment(ctx, metric.ExperimentID)
	}

	return nil
}

// GetExperimentResults 获取实验结果
func (s *ABTestingService) GetExperimentResults(ctx context.Context, experimentID string) (*ExperimentResults, error) {
	// 获取所有变体的指标
	variants, err := s.repo.GetExperimentVariants(ctx, experimentID)
	if err != nil {
		return nil, err
	}

	results := &ExperimentResults{
		ExperimentID: experimentID,
		Variants:     make([]*VariantResults, len(variants)),
	}

	for i, variant := range variants {
		metrics, err := s.repo.GetVariantMetrics(ctx, variant.ID)
		if err != nil {
			continue
		}

		// 计算统计
		results.Variants[i] = &VariantResults{
			VariantID:   variant.ID,
			VariantName: variant.Name,
			SampleSize:  len(metrics),
			AvgLatency:  calculateAvg(metrics, "latency"),
			SuccessRate: calculateRate(metrics, "success"),
			AvgCost:     calculateAvg(metrics, "cost"),
		}
	}

	// 统计显著性检验
	results.SignificanceLevel = s.calculateSignificance(results.Variants)

	return results, nil
}
```

**验收标准**:

- [ ] 实验创建和管理
- [ ] 用户分配逻辑
- [ ] 指标收集完整
- [ ] 统计分析准确

#### 2. 熔断和限流

```go
// 文件: cmd/model-router/internal/application/circuit_breaker.go

type CircuitBreaker struct {
	redis        *redis.Client
	threshold    int     // 失败阈值
	timeout      time.Duration
	halfOpenMax  int     // 半开状态最大尝试次数
}

// Allow 检查是否允许请求
func (cb *CircuitBreaker) Allow(ctx context.Context, modelID string) (bool, error) {
	state := cb.getState(ctx, modelID)

	switch state {
	case "open":
		// 熔断器打开，检查是否应该进入半开状态
		if cb.shouldHalfOpen(ctx, modelID) {
			cb.setState(ctx, modelID, "half-open")
			return true, nil
		}
		return false, fmt.Errorf("circuit breaker open for model %s", modelID)

	case "half-open":
		// 半开状态，允许少量请求
		if cb.canTryInHalfOpen(ctx, modelID) {
			return true, nil
		}
		return false, fmt.Errorf("half-open limit reached for model %s", modelID)

	case "closed":
		// 关闭状态，正常允许
		return true, nil

	default:
		return true, nil
	}
}

// RecordSuccess 记录成功
func (cb *CircuitBreaker) RecordSuccess(ctx context.Context, modelID string) {
	state := cb.getState(ctx, modelID)

	if state == "half-open" {
		// 半开状态成功，尝试关闭熔断器
		successKey := fmt.Sprintf("cb:halfopen:success:%s", modelID)
		count := cb.redis.Incr(ctx, successKey).Val()

		if count >= int64(cb.halfOpenMax) {
			cb.setState(ctx, modelID, "closed")
			cb.resetFailures(ctx, modelID)
		}
	}

	// 重置失败计数
	cb.resetFailures(ctx, modelID)
}

// RecordFailure 记录失败
func (cb *CircuitBreaker) RecordFailure(ctx context.Context, modelID string) {
	failureKey := fmt.Sprintf("cb:failures:%s", modelID)
	count := cb.redis.Incr(ctx, failureKey).Val()
	cb.redis.Expire(ctx, failureKey, cb.timeout)

	// 检查是否达到阈值
	if count >= int64(cb.threshold) {
		cb.setState(ctx, modelID, "open")
		logger.Warn("Circuit breaker opened", "model_id", modelID, "failures", count)
	}
}
```

**验收标准**:

- [ ] 熔断器正常工作
- [ ] 半开状态转换正确
- [ ] 限流机制有效

---

## 三、实施方案

### 阶段 1：核心功能（Week 1-2）

#### Day 1-5: 路由逻辑

1. 实现 4 种路由策略
2. 成本估算
3. 健康检查集成
4. 测试

#### Day 6-10: 模型注册表和健康检查

1. 模型 CRUD
2. 定时健康检查
3. 延迟统计
4. 测试

### 阶段 2：高级功能（Week 3）

#### Day 11-14: A/B 测试

1. 实验管理
2. 用户分配
3. 指标收集
4. 统计分析

#### Day 15-17: 熔断限流

1. 熔断器实现
2. 限流器实现
3. 测试

---

## 四、验收标准

### 功能验收

- [ ] 路由策略正常
- [ ] 健康检查有效
- [ ] A/B 测试可用
- [ ] 熔断限流正常

### 性能验收

- [ ] 路由决策 < 10ms
- [ ] 支持 1000 QPS
- [ ] 健康检查不影响性能

### 质量验收

- [ ] 单元测试 > 70%
- [ ] 所有 TODO 清理
- [ ] 文档完整

---

## 总结

Model Router 的主要待完成功能：

1. **路由逻辑**: 4 种策略完整实现
2. **模型注册表**: 完整的模型管理
3. **健康检查**: 定时检查和自动降级
4. **A/B 测试**: 完整的实验框架
5. **熔断限流**: 保护系统稳定

完成后将提供智能的模型路由能力。
