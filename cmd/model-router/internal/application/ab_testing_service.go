package application

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// Deprecated: ABTestConfig is deprecated, use domain.ABTestConfig instead
// This type is kept for backward compatibility only
type ABTestConfig struct {
	ID          string
	Name        string
	Description string
	StartTime   time.Time
	EndTime     time.Time
	Variants    []*ABVariant
	Enabled     bool
	CreatedAt   time.Time
}

// Deprecated: ABVariant is deprecated, use domain.ABVariant instead
// This type is kept for backward compatibility only
type ABVariant struct {
	ID          string
	Name        string
	ModelID     string
	Weight      float64 // 流量权重 (0-1)
	Description string
}

// Deprecated: ABTestResult is deprecated, use domain.ABTestResult instead
// This type is kept for backward compatibility only
type ABTestResult struct {
	VariantID    string
	RequestCount int64
	SuccessCount int64
	FailureCount int64
	AvgLatencyMs float64
	TotalTokens  int64
	TotalCost    float64
	LastUpdated  time.Time
}

// Deprecated: ABTestingService is deprecated, use ABTestingServiceV2 instead
// This implementation uses in-memory storage and will lose data on restart.
// Please migrate to ABTestingServiceV2 which provides:
// - Persistent storage (PostgreSQL + ClickHouse)
// - Repository pattern for better testability
// - Strategy pattern for variant selection
// - Redis caching for performance
// - Better observability
type ABTestingService struct {
	configs       map[string]*ABTestConfig
	results       map[string]map[string]*ABTestResult // testID -> variantID -> result
	mu            sync.RWMutex
	modelRegistry *domain.ModelRegistry
	posthog       *PostHogABTestingService // PostHog集成
	log           *log.Helper
}

// NewABTestingService 创建A/B测试服务
func NewABTestingService(modelRegistry *domain.ModelRegistry, logger log.Logger) *ABTestingService {
	return &ABTestingService{
		configs:       make(map[string]*ABTestConfig),
		results:       make(map[string]map[string]*ABTestResult),
		modelRegistry: modelRegistry,
		log:           log.NewHelper(logger),
	}
}

// NewABTestingServiceWithPostHog 创建集成PostHog的A/B测试服务
func NewABTestingServiceWithPostHog(
	modelRegistry *domain.ModelRegistry,
	posthog *PostHogABTestingService,
	logger log.Logger,
) *ABTestingService {
	return &ABTestingService{
		configs:       make(map[string]*ABTestConfig),
		results:       make(map[string]map[string]*ABTestResult),
		modelRegistry: modelRegistry,
		posthog:       posthog,
		log:           log.NewHelper(logger),
	}
}

// CreateTest 创建A/B测试
func (s *ABTestingService) CreateTest(
	ctx context.Context,
	name, description string,
	startTime, endTime time.Time,
	variants []*ABVariant,
) (*ABTestConfig, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// 验证变体权重总和为1
	totalWeight := 0.0
	for _, v := range variants {
		totalWeight += v.Weight
	}
	if totalWeight < 0.99 || totalWeight > 1.01 {
		return nil, fmt.Errorf("variant weights must sum to 1.0, got %.2f", totalWeight)
	}

	// 验证模型存在
	for _, v := range variants {
		model := s.modelRegistry.GetModel(v.ModelID)
		if model == nil {
			return nil, fmt.Errorf("model not found: %s", v.ModelID)
		}
	}

	testID := s.generateTestID(name)

	config := &ABTestConfig{
		ID:          testID,
		Name:        name,
		Description: description,
		StartTime:   startTime,
		EndTime:     endTime,
		Variants:    variants,
		Enabled:     true,
		CreatedAt:   time.Now(),
	}

	s.configs[testID] = config
	s.results[testID] = make(map[string]*ABTestResult)

	// 初始化结果
	for _, v := range variants {
		s.results[testID][v.ID] = &ABTestResult{
			VariantID:   v.ID,
			LastUpdated: time.Now(),
		}
	}

	s.log.WithContext(ctx).Infof("Created A/B test: %s (%s)", name, testID)
	return config, nil
}

// SelectVariant 为请求选择变体
func (s *ABTestingService) SelectVariant(
	ctx context.Context,
	testID, userID string,
) (*ABVariant, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	config, exists := s.configs[testID]
	if !exists {
		return nil, fmt.Errorf("test not found: %s", testID)
	}

	if !config.Enabled {
		return nil, fmt.Errorf("test disabled: %s", testID)
	}

	// 检查测试是否在有效期内
	now := time.Now()
	if now.Before(config.StartTime) || now.After(config.EndTime) {
		return nil, fmt.Errorf("test not active: %s", testID)
	}

	// 使用一致性哈希确保同一用户始终分配到同一变体
	variant := s.consistentHash(testID, userID, config.Variants)

	// PostHog事件跟踪
	if s.posthog != nil {
		properties := map[string]interface{}{
			"test_name": config.Name,
			"model_id":  variant.ModelID,
		}
		_ = s.posthog.TrackExperimentExposure(ctx, testID, variant.ID, userID, properties)
	}

	s.log.WithContext(ctx).Debugf("Selected variant %s for user %s in test %s", variant.ID, userID, testID)
	return variant, nil
}

// RecordResult 记录测试结果
func (s *ABTestingService) RecordResult(
	ctx context.Context,
	testID, variantID string,
	success bool,
	latencyMs float64,
	tokens int64,
	cost float64,
) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	results, exists := s.results[testID]
	if !exists {
		return fmt.Errorf("test not found: %s", testID)
	}

	result, exists := results[variantID]
	if !exists {
		return fmt.Errorf("variant not found: %s", variantID)
	}

	// 更新统计
	result.RequestCount++
	if success {
		result.SuccessCount++
	} else {
		result.FailureCount++
	}

	// 更新平均延迟（增量计算）
	if result.RequestCount == 1 {
		result.AvgLatencyMs = latencyMs
	} else {
		result.AvgLatencyMs = (result.AvgLatencyMs*float64(result.RequestCount-1) + latencyMs) / float64(result.RequestCount)
	}

	result.TotalTokens += tokens
	result.TotalCost += cost
	result.LastUpdated = time.Now()

	// PostHog性能指标跟踪
	if s.posthog != nil {
		metrics := &domain.ModelMetrics{
			LatencyMS:  int64(latencyMs),
			TokensUsed: int(tokens),
			Cost:       cost,
			Success:    success,
		}

		config := s.configs[testID]
		variant := s.findVariant(config, variantID)
		if variant != nil {
			// 使用空userID，因为这里不需要用户级别跟踪
			_ = s.posthog.TrackModelPerformance(ctx, "", testID, variantID, variant.ModelID, metrics)
		}
	}

	return nil
}

// findVariant 查找变体
func (s *ABTestingService) findVariant(config *ABTestConfig, variantID string) *ABVariant {
	if config == nil {
		return nil
	}
	for _, v := range config.Variants {
		if v.ID == variantID {
			return v
		}
	}
	return nil
}

// GetTestResults 获取测试结果
func (s *ABTestingService) GetTestResults(ctx context.Context, testID string) (map[string]*ABTestResult, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	results, exists := s.results[testID]
	if !exists {
		return nil, fmt.Errorf("test not found: %s", testID)
	}

	// 返回副本
	resultsCopy := make(map[string]*ABTestResult)
	for k, v := range results {
		resultsCopy[k] = &ABTestResult{
			VariantID:    v.VariantID,
			RequestCount: v.RequestCount,
			SuccessCount: v.SuccessCount,
			FailureCount: v.FailureCount,
			AvgLatencyMs: v.AvgLatencyMs,
			TotalTokens:  v.TotalTokens,
			TotalCost:    v.TotalCost,
			LastUpdated:  v.LastUpdated,
		}
	}

	return resultsCopy, nil
}

// AnalyzeTest 分析测试结果
func (s *ABTestingService) AnalyzeTest(ctx context.Context, testID string) (*ABTestAnalysis, error) {
	results, err := s.GetTestResults(ctx, testID)
	if err != nil {
		return nil, err
	}

	config := s.configs[testID]
	if config == nil {
		return nil, fmt.Errorf("test config not found: %s", testID)
	}

	analysis := &ABTestAnalysis{
		TestID:        testID,
		TestName:      config.Name,
		StartTime:     config.StartTime,
		EndTime:       config.EndTime,
		Variants:      make([]*VariantAnalysis, 0),
		TotalRequests: 0,
	}

	// 分析每个变体
	for _, variant := range config.Variants {
		result := results[variant.ID]
		if result == nil {
			continue
		}

		analysis.TotalRequests += result.RequestCount

		successRate := 0.0
		if result.RequestCount > 0 {
			successRate = float64(result.SuccessCount) / float64(result.RequestCount)
		}

		variantAnalysis := &VariantAnalysis{
			VariantID:      variant.ID,
			VariantName:    variant.Name,
			ModelID:        variant.ModelID,
			Weight:         variant.Weight,
			RequestCount:   result.RequestCount,
			SuccessRate:    successRate,
			AvgLatencyMs:   result.AvgLatencyMs,
			TotalCost:      result.TotalCost,
			CostPerRequest: 0,
		}

		if result.RequestCount > 0 {
			variantAnalysis.CostPerRequest = result.TotalCost / float64(result.RequestCount)
		}

		analysis.Variants = append(analysis.Variants, variantAnalysis)
	}

	// 找出最优变体
	analysis.BestVariant = s.determineBestVariant(analysis.Variants)

	return analysis, nil
}

// StopTest 停止测试
func (s *ABTestingService) StopTest(ctx context.Context, testID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	config, exists := s.configs[testID]
	if !exists {
		return fmt.Errorf("test not found: %s", testID)
	}

	config.Enabled = false
	s.log.WithContext(ctx).Infof("Stopped A/B test: %s", testID)

	return nil
}

// ListTests 列出所有测试
func (s *ABTestingService) ListTests(ctx context.Context) []*ABTestConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()

	tests := make([]*ABTestConfig, 0, len(s.configs))
	for _, config := range s.configs {
		tests = append(tests, config)
	}

	return tests
}

// consistentHash 使用一致性哈希分配变体
func (s *ABTestingService) consistentHash(testID, userID string, variants []*ABVariant) *ABVariant {
	// 生成哈希值
	hash := sha256.Sum256([]byte(testID + ":" + userID))
	hashStr := hex.EncodeToString(hash[:])

	// 转换为0-1之间的浮点数
	hashValue := float64(hash[0]) / 256.0

	// 根据权重选择变体
	cumulative := 0.0
	for _, v := range variants {
		cumulative += v.Weight
		if hashValue <= cumulative {
			return v
		}
	}

	// 兜底返回最后一个
	return variants[len(variants)-1]
}

// generateTestID 生成测试ID
func (s *ABTestingService) generateTestID(name string) string {
	timestamp := time.Now().Unix()
	return fmt.Sprintf("test_%d_%s", timestamp, name)
}

// determineBestVariant 确定最优变体
func (s *ABTestingService) determineBestVariant(variants []*VariantAnalysis) *VariantAnalysis {
	if len(variants) == 0 {
		return nil
	}

	// 综合评分：成功率(40%) + 延迟(30%) + 成本(30%)
	var best *VariantAnalysis
	bestScore := -1.0

	for _, v := range variants {
		if v.RequestCount < 10 {
			// 样本太少，跳过
			continue
		}

		// 成功率分数
		successScore := v.SuccessRate * 0.4

		// 延迟分数（越低越好，归一化）
		latencyScore := 0.0
		if v.AvgLatencyMs > 0 {
			latencyScore = (1.0 / v.AvgLatencyMs) * 0.3 * 1000 // 归一化
		}

		// 成本分数（越低越好）
		costScore := 0.0
		if v.CostPerRequest > 0 {
			costScore = (1.0 / v.CostPerRequest) * 0.3 * 0.1 // 归一化
		}

		score := successScore + latencyScore + costScore

		if score > bestScore {
			bestScore = score
			best = v
		}
	}

	return best
}

// ABTestAnalysis A/B测试分析结果
type ABTestAnalysis struct {
	TestID        string
	TestName      string
	StartTime     time.Time
	EndTime       time.Time
	TotalRequests int64
	Variants      []*VariantAnalysis
	BestVariant   *VariantAnalysis
}

// VariantAnalysis 变体分析
type VariantAnalysis struct {
	VariantID      string
	VariantName    string
	ModelID        string
	Weight         float64
	RequestCount   int64
	SuccessRate    float64
	AvgLatencyMs   float64
	TotalCost      float64
	CostPerRequest float64
}
