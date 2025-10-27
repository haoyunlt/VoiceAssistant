package application

import (
	"context"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/posthog/posthog-go"
	"voiceassistant/model-router/internal/domain"
)

// PostHogABTestingService PostHog A/B测试服务
// 集成PostHog开源A/B测试框架，提供特性标志和实验功能
type PostHogABTestingService struct {
	client   posthog.Client
	logger   *log.Helper
	enabled  bool
	projectKey string
}

// PostHogConfig PostHog配置
type PostHogConfig struct {
	APIKey     string
	Host       string // 默认: https://app.posthog.com 或自托管地址
	ProjectKey string
	Enabled    bool
}

// NewPostHogABTestingService 创建PostHog A/B测试服务
func NewPostHogABTestingService(config PostHogConfig, logger log.Logger) (*PostHogABTestingService, error) {
	logHelper := log.NewHelper(log.With(logger, "module", "posthog_ab_testing"))

	if !config.Enabled {
		logHelper.Info("PostHog A/B testing is disabled")
		return &PostHogABTestingService{
			enabled: false,
			logger:  logHelper,
		}, nil
	}

	// 设置默认Host
	if config.Host == "" {
		config.Host = "https://app.posthog.com"
	}

	// 创建PostHog客户端
	client, err := posthog.NewWithConfig(
		config.APIKey,
		posthog.Config{
			Endpoint: config.Host,
			// 批量发送配置
			BatchSize: 100,
			Interval:  30 * time.Second,
			// 启用压缩
			DefaultFeatureFlagsPollingInterval: 30 * time.Second,
		},
	)

	if err != nil {
		logHelper.Errorf("failed to create PostHog client: %v", err)
		return nil, fmt.Errorf("failed to create PostHog client: %w", err)
	}

	logHelper.Infof("PostHog A/B testing service initialized with host: %s", config.Host)

	return &PostHogABTestingService{
		client:     client,
		logger:     logHelper,
		enabled:    true,
		projectKey: config.ProjectKey,
	}, nil
}

// IsFeatureEnabled 检查特性标志是否启用
func (s *PostHogABTestingService) IsFeatureEnabled(
	ctx context.Context,
	featureKey string,
	userID string,
	userProperties map[string]interface{},
) (bool, error) {
	if !s.enabled {
		return false, nil
	}

	// 使用PostHog的特性标志功能
	enabled, err := s.client.IsFeatureEnabled(
		posthog.FeatureFlagPayload{
			Key:        featureKey,
			DistinctId: userID,
			PersonProperties: userProperties,
		},
	)

	if err != nil {
		s.logger.Errorf("failed to check feature flag %s: %v", featureKey, err)
		return false, err
	}

	s.logger.Debugf("feature flag %s for user %s: %v", featureKey, userID, enabled)
	return enabled, nil
}

// GetFeatureFlagVariant 获取特性标志变体
// 用于多变体A/B测试（如 A/B/C 测试）
func (s *PostHogABTestingService) GetFeatureFlagVariant(
	ctx context.Context,
	featureKey string,
	userID string,
	userProperties map[string]interface{},
) (string, error) {
	if !s.enabled {
		return "control", nil
	}

	variant, err := s.client.GetFeatureFlag(
		posthog.FeatureFlagPayload{
			Key:        featureKey,
			DistinctId: userID,
			PersonProperties: userProperties,
		},
	)

	if err != nil {
		s.logger.Errorf("failed to get feature flag variant %s: %v", featureKey, err)
		return "", err
	}

	// variant 可能是 boolean, string, 或 nil
	variantStr, ok := variant.(string)
	if !ok {
		if boolVariant, isBool := variant.(bool); isBool {
			if boolVariant {
				return "test", nil
			}
			return "control", nil
		}
		return "control", nil
	}

	s.logger.Debugf("feature flag variant %s for user %s: %s", featureKey, userID, variantStr)
	return variantStr, nil
}

// TrackExperimentExposure 跟踪实验曝光
func (s *PostHogABTestingService) TrackExperimentExposure(
	ctx context.Context,
	experimentKey string,
	variantKey string,
	userID string,
	properties map[string]interface{},
) error {
	if !s.enabled {
		return nil
	}

	// 确保properties不为nil
	if properties == nil {
		properties = make(map[string]interface{})
	}

	// 添加实验信息
	properties["experiment_key"] = experimentKey
	properties["variant_key"] = variantKey

	err := s.client.Enqueue(posthog.Capture{
		DistinctId: userID,
		Event:      "$experiment_exposure",
		Properties: properties,
		Timestamp:  time.Now(),
	})

	if err != nil {
		s.logger.Errorf("failed to track experiment exposure: %v", err)
		return err
	}

	s.logger.Debugf("tracked experiment exposure for user %s: %s/%s", userID, experimentKey, variantKey)
	return nil
}

// TrackEvent 跟踪自定义事件
func (s *PostHogABTestingService) TrackEvent(
	ctx context.Context,
	eventName string,
	userID string,
	properties map[string]interface{},
) error {
	if !s.enabled {
		return nil
	}

	if properties == nil {
		properties = make(map[string]interface{})
	}

	err := s.client.Enqueue(posthog.Capture{
		DistinctId: userID,
		Event:      eventName,
		Properties: properties,
		Timestamp:  time.Now(),
	})

	if err != nil {
		s.logger.Errorf("failed to track event %s: %v", eventName, err)
		return err
	}

	s.logger.Debugf("tracked event %s for user %s", eventName, userID)
	return nil
}

// IdentifyUser 识别用户并设置用户属性
func (s *PostHogABTestingService) IdentifyUser(
	ctx context.Context,
	userID string,
	properties map[string]interface{},
) error {
	if !s.enabled {
		return nil
	}

	err := s.client.Enqueue(posthog.Identify{
		DistinctId: userID,
		Properties: properties,
		Timestamp:  time.Now(),
	})

	if err != nil {
		s.logger.Errorf("failed to identify user %s: %v", userID, err)
		return err
	}

	s.logger.Debugf("identified user %s with properties", userID)
	return nil
}

// TrackModelSelection 跟踪模型选择事件（特定于Model Router）
func (s *PostHogABTestingService) TrackModelSelection(
	ctx context.Context,
	userID string,
	experimentID string,
	variantID string,
	selectedModel string,
	requestType string,
	properties map[string]interface{},
) error {
	if !s.enabled {
		return nil
	}

	if properties == nil {
		properties = make(map[string]interface{})
	}

	// 添加模型路由特定信息
	properties["experiment_id"] = experimentID
	properties["variant_id"] = variantID
	properties["selected_model"] = selectedModel
	properties["request_type"] = requestType

	return s.TrackEvent(ctx, "model_selected", userID, properties)
}

// TrackModelPerformance 跟踪模型性能指标
func (s *PostHogABTestingService) TrackModelPerformance(
	ctx context.Context,
	userID string,
	experimentID string,
	variantID string,
	modelID string,
	metrics *domain.ModelMetrics,
) error {
	if !s.enabled {
		return nil
	}

	properties := map[string]interface{}{
		"experiment_id":  experimentID,
		"variant_id":     variantID,
		"model_id":       modelID,
		"latency_ms":     metrics.LatencyMS,
		"tokens_used":    metrics.TokensUsed,
		"cost":           metrics.Cost,
		"success":        metrics.Success,
		"error_code":     metrics.ErrorCode,
		"error_message":  metrics.ErrorMessage,
	}

	return s.TrackEvent(ctx, "model_performance", userID, properties)
}

// Close 关闭PostHog客户端
func (s *PostHogABTestingService) Close() error {
	if !s.enabled || s.client == nil {
		return nil
	}

	// 确保所有事件都被发送
	err := s.client.Close()
	if err != nil {
		s.logger.Errorf("failed to close PostHog client: %v", err)
		return err
	}

	s.logger.Info("PostHog client closed")
	return nil
}

// GetAllFeatureFlags 获取用户的所有特性标志
func (s *PostHogABTestingService) GetAllFeatureFlags(
	ctx context.Context,
	userID string,
	userProperties map[string]interface{},
) (map[string]interface{}, error) {
	if !s.enabled {
		return nil, nil
	}

	flags, err := s.client.GetAllFlags(posthog.FeatureFlagPayloadNoKey{
		DistinctId:       userID,
		PersonProperties: userProperties,
	})

	if err != nil {
		s.logger.Errorf("failed to get all feature flags for user %s: %v", userID, err)
		return nil, err
	}

	s.logger.Debugf("retrieved %d feature flags for user %s", len(flags), userID)
	return flags, nil
}

// ReloadFeatureFlags 重新加载特性标志（用于及时获取最新配置）
func (s *PostHogABTestingService) ReloadFeatureFlags(ctx context.Context) error {
	if !s.enabled {
		return nil
	}

	err := s.client.ReloadFeatureFlags()
	if err != nil {
		s.logger.Errorf("failed to reload feature flags: %v", err)
		return err
	}

	s.logger.Info("feature flags reloaded")
	return nil
}
