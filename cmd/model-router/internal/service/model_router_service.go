package service

import (
	"context"
	"fmt"

	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ModelRouterService 模型路由服务
type ModelRouterService struct {
	routingService  *application.RoutingService
	abTestService   *application.ABTestingServiceV2
	costOptimizer   *application.CostOptimizer
	fallbackManager *application.FallbackManager
	logger          log.Logger
}

// NewModelRouterService 创建模型路由服务
func NewModelRouterService(
	routingService *application.RoutingService,
	abTestService *application.ABTestingServiceV2,
	costOptimizer *application.CostOptimizer,
	fallbackManager *application.FallbackManager,
	logger log.Logger,
) *ModelRouterService {
	return &ModelRouterService{
		routingService:  routingService,
		abTestService:   abTestService,
		costOptimizer:   costOptimizer,
		fallbackManager: fallbackManager,
		logger:          logger,
	}
}

// RouteRequest 路由请求（简化版本）
func (s *ModelRouterService) RouteRequest(ctx context.Context, req *application.RoutingRequest) (*application.RoutingResponse, error) {
	helper := log.NewHelper(s.logger)
	helper.Infof("Routing request with strategy: %s", req.Strategy)

	// 使用路由服务进行路由
	result, err := s.routingService.Route(ctx, req)
	if err != nil {
		helper.Errorf("Routing failed: %v", err)
		return nil, err
	}

	return result, nil
}

// GetModelRegistry 获取模型注册表（简化版本）
func (s *ModelRouterService) GetModelRegistry() *domain.ModelRegistry {
	// 返回 nil，实际应该从 routingService 获取
	return nil
}

// CreateABTest 创建 A/B 测试
func (s *ModelRouterService) CreateABTest(ctx context.Context, req *application.CreateTestRequest) (*domain.ABTestConfig, error) {
	return s.abTestService.CreateTest(ctx, req)
}

// StartABTest 启动 A/B 测试
func (s *ModelRouterService) StartABTest(ctx context.Context, testID string) error {
	return s.abTestService.StartTest(ctx, testID)
}

// StopABTest 停止 A/B 测试
func (s *ModelRouterService) StopABTest(ctx context.Context, testID string) error {
	return s.abTestService.PauseTest(ctx, testID)
}

// GetABTestResults 获取 A/B 测试结果
func (s *ModelRouterService) GetABTestResults(ctx context.Context, testID string) (map[string]interface{}, error) {
	results, err := s.abTestService.GetTestResults(ctx, testID)
	if err != nil {
		return nil, err
	}

	// 转换为 map[string]interface{}
	resultMap := make(map[string]interface{})
	resultMap["test_id"] = testID
	resultMap["variants"] = results

	return resultMap, nil
}

// ListABTests 列出所有 A/B 测试
func (s *ModelRouterService) ListABTests(ctx context.Context) ([]*domain.ABTestConfig, error) {
	return s.abTestService.ListTests(ctx, nil)
}

// GetABTest 获取单个 A/B 测试
func (s *ModelRouterService) GetABTest(ctx context.Context, testID string) (*domain.ABTestConfig, error) {
	// TODO: 实现获取测试
	return nil, fmt.Errorf("not implemented")
}

// DeleteABTest 删除 A/B 测试
func (s *ModelRouterService) DeleteABTest(ctx context.Context, testID string) error {
	return fmt.Errorf("not implemented")
}

// RecordMetrics 记录指标
func (s *ModelRouterService) RecordMetrics(ctx context.Context, testID, variantID, userID string, success bool, latency int, tokens int, cost float64) error {
	// TODO: 实现指标记录
	return nil
}
