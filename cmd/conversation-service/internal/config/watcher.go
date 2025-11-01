package config

import (
	"context"
	"sync"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/nacos-group/nacos-sdk-go/v2/clients/config_client"
	"github.com/nacos-group/nacos-sdk-go/v2/vo"
)

// ConfigWatcher 配置监听器
type ConfigWatcher struct {
	client   config_client.IConfigClient
	logger   *log.Helper
	handlers map[string][]ChangeHandler
	mu       sync.RWMutex
	ctx      context.Context
	cancel   context.CancelFunc
}

// ChangeHandler 配置变更处理器
type ChangeHandler func(namespace, group, dataId, content string)

// NewConfigWatcher 创建配置监听器
func NewConfigWatcher(client config_client.IConfigClient, logger log.Logger) *ConfigWatcher {
	ctx, cancel := context.WithCancel(context.Background())

	return &ConfigWatcher{
		client:   client,
		logger:   log.NewHelper(log.With(logger, "module", "config-watcher")),
		handlers: make(map[string][]ChangeHandler),
		ctx:      ctx,
		cancel:   cancel,
	}
}

// Watch 监听配置变更
func (cw *ConfigWatcher) Watch(namespace, group, dataId string) error {
	cw.logger.Infof("Start watching config: namespace=%s, group=%s, dataId=%s",
		namespace, group, dataId)

	// 注册监听器
	err := cw.client.ListenConfig(vo.ConfigParam{
		DataId: dataId,
		Group:  group,
		OnChange: func(namespace, group, dataId, data string) {
			cw.logger.Infof("Config changed: namespace=%s, group=%s, dataId=%s",
				namespace, group, dataId)

			// 调用所有注册的处理器
			cw.mu.RLock()
			key := cw.getKey(namespace, group, dataId)
			handlers, ok := cw.handlers[key]
			cw.mu.RUnlock()

			if ok {
				for _, handler := range handlers {
					go func(h ChangeHandler) {
						defer func() {
							if r := recover(); r != nil {
								cw.logger.Errorf("Config change handler panic: %v", r)
							}
						}()
						h(namespace, group, dataId, data)
					}(handler)
				}
			}
		},
	})

	if err != nil {
		return err
	}

	return nil
}

// RegisterHandler 注册配置变更处理器
func (cw *ConfigWatcher) RegisterHandler(namespace, group, dataId string, handler ChangeHandler) {
	cw.mu.Lock()
	defer cw.mu.Unlock()

	key := cw.getKey(namespace, group, dataId)
	cw.handlers[key] = append(cw.handlers[key], handler)

	cw.logger.Debugf("Registered config handler: key=%s", key)
}

// UnregisterHandler 取消注册配置变更处理器
func (cw *ConfigWatcher) UnregisterHandler(namespace, group, dataId string) {
	cw.mu.Lock()
	defer cw.mu.Unlock()

	key := cw.getKey(namespace, group, dataId)
	delete(cw.handlers, key)

	cw.logger.Debugf("Unregistered config handler: key=%s", key)
}

// Stop 停止监听
func (cw *ConfigWatcher) Stop() {
	cw.cancel()
	cw.logger.Info("Config watcher stopped")
}

// getKey 生成键
func (cw *ConfigWatcher) getKey(namespace, group, dataId string) string {
	return namespace + ":" + group + ":" + dataId
}

// HotReloadableConfig 支持热更新的配置
type HotReloadableConfig struct {
	mu     sync.RWMutex
	config interface{}
	logger *log.Helper
}

// NewHotReloadableConfig 创建支持热更新的配置
func NewHotReloadableConfig(initialConfig interface{}, logger log.Logger) *HotReloadableConfig {
	return &HotReloadableConfig{
		config: initialConfig,
		logger: log.NewHelper(log.With(logger, "module", "hot-reloadable-config")),
	}
}

// Get 获取配置
func (hrc *HotReloadableConfig) Get() interface{} {
	hrc.mu.RLock()
	defer hrc.mu.RUnlock()
	return hrc.config
}

// Update 更新配置
func (hrc *HotReloadableConfig) Update(newConfig interface{}) {
	hrc.mu.Lock()
	defer hrc.mu.Unlock()

	hrc.config = newConfig
	hrc.logger.Info("Config updated successfully")
}

// RateLimitConfigManager 限流配置管理器（支持热更新）
type RateLimitConfigManager struct {
	config *HotReloadableConfig
	logger *log.Helper
}

// RateLimitConfig 限流配置
type RateLimitConfig struct {
	RequestsPerSecond int           `json:"requests_per_second"`
	BurstSize         int           `json:"burst_size"`
	TTL               time.Duration `json:"ttl"`
	Enabled           bool          `json:"enabled"`
}

// NewRateLimitConfigManager 创建限流配置管理器
func NewRateLimitConfigManager(initialConfig *RateLimitConfig, logger log.Logger) *RateLimitConfigManager {
	return &RateLimitConfigManager{
		config: NewHotReloadableConfig(initialConfig, logger),
		logger: log.NewHelper(log.With(logger, "module", "ratelimit-config-manager")),
	}
}

// GetConfig 获取配置
func (rcm *RateLimitConfigManager) GetConfig() *RateLimitConfig {
	return rcm.config.Get().(*RateLimitConfig)
}

// UpdateConfig 更新配置
func (rcm *RateLimitConfigManager) UpdateConfig(newConfig *RateLimitConfig) {
	rcm.config.Update(newConfig)
	rcm.logger.Infof("Rate limit config updated: rps=%d, burst=%d, enabled=%v",
		newConfig.RequestsPerSecond, newConfig.BurstSize, newConfig.Enabled)
}

// FeatureFlagManager 功能开关管理器（支持热更新）
type FeatureFlagManager struct {
	flags  sync.Map
	logger *log.Helper
}

// NewFeatureFlagManager 创建功能开关管理器
func NewFeatureFlagManager(logger log.Logger) *FeatureFlagManager {
	return &FeatureFlagManager{
		logger: log.NewHelper(log.With(logger, "module", "feature-flag-manager")),
	}
}

// IsEnabled 检查功能是否启用
func (ffm *FeatureFlagManager) IsEnabled(feature string) bool {
	if value, ok := ffm.flags.Load(feature); ok {
		return value.(bool)
	}
	return false
}

// SetFlag 设置功能开关
func (ffm *FeatureFlagManager) SetFlag(feature string, enabled bool) {
	ffm.flags.Store(feature, enabled)
	ffm.logger.Infof("Feature flag updated: %s=%v", feature, enabled)
}

// GetAllFlags 获取所有功能开关
func (ffm *FeatureFlagManager) GetAllFlags() map[string]bool {
	flags := make(map[string]bool)
	ffm.flags.Range(func(key, value interface{}) bool {
		flags[key.(string)] = value.(bool)
		return true
	})
	return flags
}

// LoadFromMap 从 map 加载功能开关
func (ffm *FeatureFlagManager) LoadFromMap(flags map[string]bool) {
	for feature, enabled := range flags {
		ffm.SetFlag(feature, enabled)
	}
	ffm.logger.Infof("Loaded %d feature flags", len(flags))
}

// CircuitBreakerConfigManager 熔断器配置管理器（支持热更新）
type CircuitBreakerConfigManager struct {
	config *HotReloadableConfig
	logger *log.Helper
}

// CircuitBreakerConfig 熔断器配置
type CircuitBreakerConfig struct {
	MaxRequests       uint32        `json:"max_requests"`
	Interval          time.Duration `json:"interval"`
	Timeout           time.Duration `json:"timeout"`
	FailureRatio      float64       `json:"failure_ratio"`
	SuccessThreshold  uint32        `json:"success_threshold"`
	Enabled           bool          `json:"enabled"`
}

// NewCircuitBreakerConfigManager 创建熔断器配置管理器
func NewCircuitBreakerConfigManager(
	initialConfig *CircuitBreakerConfig,
	logger log.Logger,
) *CircuitBreakerConfigManager {
	return &CircuitBreakerConfigManager{
		config: NewHotReloadableConfig(initialConfig, logger),
		logger: log.NewHelper(log.With(logger, "module", "circuitbreaker-config-manager")),
	}
}

// GetConfig 获取配置
func (ccm *CircuitBreakerConfigManager) GetConfig() *CircuitBreakerConfig {
	return ccm.config.Get().(*CircuitBreakerConfig)
}

// UpdateConfig 更新配置
func (ccm *CircuitBreakerConfigManager) UpdateConfig(newConfig *CircuitBreakerConfig) {
	ccm.config.Update(newConfig)
	ccm.logger.Infof("Circuit breaker config updated: max_requests=%d, failure_ratio=%.2f, enabled=%v",
		newConfig.MaxRequests, newConfig.FailureRatio, newConfig.Enabled)
}

// DynamicConfig 动态配置管理器（统一管理所有热更新配置）
type DynamicConfig struct {
	watcher              *ConfigWatcher
	rateLimitConfig      *RateLimitConfigManager
	featureFlags         *FeatureFlagManager
	circuitBreakerConfig *CircuitBreakerConfigManager
	logger               *log.Helper
}

// NewDynamicConfig 创建动态配置管理器
func NewDynamicConfig(
	watcher *ConfigWatcher,
	rateLimitConfig *RateLimitConfigManager,
	featureFlags *FeatureFlagManager,
	circuitBreakerConfig *CircuitBreakerConfigManager,
	logger log.Logger,
) *DynamicConfig {
	return &DynamicConfig{
		watcher:              watcher,
		rateLimitConfig:      rateLimitConfig,
		featureFlags:         featureFlags,
		circuitBreakerConfig: circuitBreakerConfig,
		logger:               log.NewHelper(log.With(logger, "module", "dynamic-config")),
	}
}

// Start 启动配置监听
func (dc *DynamicConfig) Start(namespace, group string) error {
	// 监听限流配置
	if err := dc.watcher.Watch(namespace, group, "rate_limit_config"); err != nil {
		return err
	}
	dc.watcher.RegisterHandler(namespace, group, "rate_limit_config",
		func(ns, g, dataId, content string) {
			dc.logger.Infof("Rate limit config changed")
			// 解析并更新配置
			// var newConfig RateLimitConfig
			// ... 解析 content ...
			// dc.rateLimitConfig.UpdateConfig(&newConfig)
		})

	// 监听功能开关
	if err := dc.watcher.Watch(namespace, group, "feature_flags"); err != nil {
		return err
	}
	dc.watcher.RegisterHandler(namespace, group, "feature_flags",
		func(ns, g, dataId, content string) {
			dc.logger.Infof("Feature flags changed")
			// 解析并更新功能开关
			// var flags map[string]bool
			// ... 解析 content ...
			// dc.featureFlags.LoadFromMap(flags)
		})

	// 监听熔断器配置
	if err := dc.watcher.Watch(namespace, group, "circuit_breaker_config"); err != nil {
		return err
	}
	dc.watcher.RegisterHandler(namespace, group, "circuit_breaker_config",
		func(ns, g, dataId, content string) {
			dc.logger.Infof("Circuit breaker config changed")
			// 解析并更新配置
			// var newConfig CircuitBreakerConfig
			// ... 解析 content ...
			// dc.circuitBreakerConfig.UpdateConfig(&newConfig)
		})

	dc.logger.Info("Dynamic config started")
	return nil
}

// Stop 停止配置监听
func (dc *DynamicConfig) Stop() {
	dc.watcher.Stop()
	dc.logger.Info("Dynamic config stopped")
}

// GetRateLimitConfig 获取限流配置
func (dc *DynamicConfig) GetRateLimitConfig() *RateLimitConfig {
	return dc.rateLimitConfig.GetConfig()
}

// GetFeatureFlags 获取功能开关
func (dc *DynamicConfig) GetFeatureFlags() *FeatureFlagManager {
	return dc.featureFlags
}

// GetCircuitBreakerConfig 获取熔断器配置
func (dc *DynamicConfig) GetCircuitBreakerConfig() *CircuitBreakerConfig {
	return dc.circuitBreakerConfig.GetConfig()
}

