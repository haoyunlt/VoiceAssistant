package application

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/uuid"
)

// ABTestCache 缓存接口（临时定义，实际应在infrastructure包中）
type ABTestCache interface {
	GetUserVariant(ctx context.Context, testID, userID string) (*domain.ABVariant, error)
	SetUserVariant(ctx context.Context, testID, userID string, variant *domain.ABVariant, ttl time.Duration) error
	GetTest(ctx context.Context, testID string) (*domain.ABTestConfig, error)
	SetTest(ctx context.Context, test *domain.ABTestConfig, ttl time.Duration) error
	InvalidateTest(ctx context.Context, testID string) error
	InvalidateUserVariant(ctx context.Context, testID, userID string) error
}

// ABTestingServiceV2 重构后的A/B测试服务
type ABTestingServiceV2 struct {
	repo          domain.ABTestRepository
	cache         ABTestCache
	modelRegistry *domain.ModelRegistry
	selectors     map[string]VariantSelector
	log           *log.Helper
}

// NewABTestingServiceV2 创建A/B测试服务V2
func NewABTestingServiceV2(
	repo domain.ABTestRepository,
	cache ABTestCache,
	modelRegistry *domain.ModelRegistry,
	logger log.Logger,
) *ABTestingServiceV2 {
	return &ABTestingServiceV2{
		repo:          repo,
		cache:         cache,
		modelRegistry: modelRegistry,
		log:           log.NewHelper(logger),
		selectors: map[string]VariantSelector{
			"consistent_hash": NewConsistentHashSelector(),
			"weighted_random": NewWeightedRandomSelector(),
		},
	}
}

// CreateTestRequest 创建测试请求
type CreateTestRequest struct {
	Name        string
	Description string
	StartTime   time.Time
	EndTime     time.Time
	Strategy    string
	Variants    []*domain.ABVariant
	CreatedBy   string
}

// CreateTest 创建A/B测试
func (s *ABTestingServiceV2) CreateTest(
	ctx context.Context,
	req *CreateTestRequest,
) (*domain.ABTestConfig, error) {
	// 1. 验证请求
	if err := s.validateTestRequest(req); err != nil {
		return nil, err
	}

	// 2. 创建测试配置
	test := &domain.ABTestConfig{
		ID:          fmt.Sprintf("test_%s", uuid.New().String()[:8]),
		Name:        req.Name,
		Description: req.Description,
		StartTime:   req.StartTime,
		EndTime:     req.EndTime,
		Status:      domain.TestStatusDraft,
		Strategy:    req.Strategy,
		Variants:    req.Variants,
		Metadata:    make(map[string]interface{}),
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
		CreatedBy:   req.CreatedBy,
	}

	// 3. 持久化
	if err := s.repo.CreateTest(ctx, test); err != nil {
		return nil, err
	}

	s.log.WithContext(ctx).Infof("A/B test created: %s (%s)", test.Name, test.ID)

	return test, nil
}

// StartTest 启动测试
func (s *ABTestingServiceV2) StartTest(ctx context.Context, testID string) error {
	// 1. 获取测试
	test, err := s.repo.GetTest(ctx, testID)
	if err != nil {
		return err
	}

	// 2. 验证状态
	if test.Status != domain.TestStatusDraft && test.Status != domain.TestStatusPaused {
		return fmt.Errorf("cannot start test in status: %s", test.Status)
	}

	// 3. 验证时间范围
	now := time.Now()
	if now.After(test.EndTime) {
		return fmt.Errorf("test end time has passed")
	}

	// 4. 更新状态
	test.Status = domain.TestStatusRunning
	test.UpdatedAt = time.Now()

	if err := s.repo.UpdateTest(ctx, test); err != nil {
		return err
	}

	// 5. 缓存测试配置
	duration := test.EndTime.Sub(now)
	_ = s.cache.SetTest(ctx, test, duration)

	s.log.WithContext(ctx).Infof("A/B test started: %s", testID)

	return nil
}

// PauseTest 暂停测试
func (s *ABTestingServiceV2) PauseTest(ctx context.Context, testID string) error {
	test, err := s.repo.GetTest(ctx, testID)
	if err != nil {
		return err
	}

	if test.Status != domain.TestStatusRunning {
		return fmt.Errorf("can only pause running tests")
	}

	test.Status = domain.TestStatusPaused
	test.UpdatedAt = time.Now()

	if err := s.repo.UpdateTest(ctx, test); err != nil {
		return err
	}

	// 清除缓存
	_ = s.cache.InvalidateTest(ctx, testID)

	s.log.WithContext(ctx).Infof("A/B test paused: %s", testID)

	return nil
}

// CompleteTest 完成测试
func (s *ABTestingServiceV2) CompleteTest(ctx context.Context, testID string) error {
	test, err := s.repo.GetTest(ctx, testID)
	if err != nil {
		return err
	}

	test.Status = domain.TestStatusCompleted
	test.UpdatedAt = time.Now()

	if err := s.repo.UpdateTest(ctx, test); err != nil {
		return err
	}

	// 清除缓存
	_ = s.cache.InvalidateTest(ctx, testID)

	s.log.WithContext(ctx).Infof("A/B test completed: %s", testID)

	return nil
}

// SelectVariant 为请求选择变体
func (s *ABTestingServiceV2) SelectVariant(
	ctx context.Context,
	testID, userID string,
) (*domain.ABVariant, error) {
	// 1. 尝试从缓存获取用户已分配的变体
	cachedVariant, err := s.cache.GetUserVariant(ctx, testID, userID)
	if err == nil && cachedVariant != nil {
		s.log.WithContext(ctx).Debugf("Cache hit for user variant: test=%s, user=%s", testID, userID)
		return cachedVariant, nil
	}

	// 2. 获取测试配置（优先从缓存）
	test, err := s.getTestConfig(ctx, testID)
	if err != nil {
		return nil, err
	}

	// 3. 验证测试状态
	if !test.IsActive() {
		return nil, domain.ErrTestNotActive
	}

	// 4. 使用策略选择变体
	selector := s.getSelector(test.Strategy)
	variant, err := selector.Select(testID, userID, test.Variants)
	if err != nil {
		return nil, err
	}

	// 5. 缓存用户的变体分配（确保一致性）
	ttl := test.EndTime.Sub(time.Now())
	_ = s.cache.SetUserVariant(ctx, testID, userID, variant, ttl)

	s.log.WithContext(ctx).Debugf("Selected variant %s for user %s in test %s", variant.ID, userID, testID)

	return variant, nil
}

// RecordResult 记录测试结果
func (s *ABTestingServiceV2) RecordResult(
	ctx context.Context,
	testID, variantID, userID string,
	success bool,
	latencyMs float64,
	tokens int64,
	cost float64,
) error {
	metric := &domain.ABTestMetric{
		ID:         uuid.New().String(),
		TestID:     testID,
		VariantID:  variantID,
		UserID:     userID,
		Timestamp:  time.Now(),
		Success:    success,
		LatencyMs:  latencyMs,
		TokensUsed: tokens,
		CostUSD:    cost,
	}

	return s.repo.RecordMetric(ctx, metric)
}

// GetTestResults 获取测试结果
func (s *ABTestingServiceV2) GetTestResults(
	ctx context.Context,
	testID string,
) (map[string]*domain.ABTestResult, error) {
	// 验证测试存在
	_, err := s.repo.GetTest(ctx, testID)
	if err != nil {
		return nil, err
	}

	// 聚合查询结果
	return s.repo.AggregateResults(ctx, testID)
}

// ListTests 列出所有测试
func (s *ABTestingServiceV2) ListTests(
	ctx context.Context,
	filters *domain.TestFilters,
) ([]*domain.ABTestConfig, error) {
	return s.repo.ListTests(ctx, filters)
}

// DeleteTest 删除测试
func (s *ABTestingServiceV2) DeleteTest(ctx context.Context, testID string) error {
	// 清除缓存
	_ = s.cache.InvalidateTest(ctx, testID)

	return s.repo.DeleteTest(ctx, testID)
}

// getTestConfig 获取测试配置（优先从缓存）
func (s *ABTestingServiceV2) getTestConfig(ctx context.Context, testID string) (*domain.ABTestConfig, error) {
	// 尝试从缓存获取
	test, err := s.cache.GetTest(ctx, testID)
	if err == nil && test != nil {
		return test, nil
	}

	// 缓存未命中，从数据库读取
	test, err = s.repo.GetTest(ctx, testID)
	if err != nil {
		return nil, err
	}

	// 更新缓存
	if test.IsActive() {
		ttl := test.EndTime.Sub(time.Now())
		_ = s.cache.SetTest(ctx, test, ttl)
	}

	return test, nil
}

// getSelector 获取变体选择器
func (s *ABTestingServiceV2) getSelector(strategy string) VariantSelector {
	selector, exists := s.selectors[strategy]
	if !exists {
		// 默认使用一致性哈希
		selector = s.selectors["consistent_hash"]
	}
	return selector
}

// validateTestRequest 验证请求
func (s *ABTestingServiceV2) validateTestRequest(req *CreateTestRequest) error {
	// 验证名称
	if req.Name == "" {
		return fmt.Errorf("test name is required")
	}

	// 验证时间范围
	if req.EndTime.Before(req.StartTime) {
		return domain.ErrInvalidTimeRange
	}

	// 验证变体
	if len(req.Variants) == 0 {
		return domain.ErrInvalidVariants
	}

	// 验证权重总和
	totalWeight := 0.0
	for _, v := range req.Variants {
		if v.Weight < 0 || v.Weight > 1 {
			return domain.ErrInvalidWeight
		}
		totalWeight += v.Weight
	}
	if totalWeight < 0.99 || totalWeight > 1.01 {
		return domain.ErrInvalidTotalWeight
	}

	// 验证模型存在
	for _, v := range req.Variants {
		model := s.modelRegistry.GetModel(v.ModelID)
		if model == nil {
			return fmt.Errorf("%w: %s", domain.ErrModelNotFound, v.ModelID)
		}
	}

	// 验证策略
	if req.Strategy == "" {
		req.Strategy = "consistent_hash"
	}

	return nil
}
