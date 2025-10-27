package application

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
	"voiceassistant/cmd/model-router/internal/domain"
)

// DynamicModelLoader 动态模型加载器
type DynamicModelLoader struct {
	registry       *domain.ModelRegistry
	configPath     string
	reloadInterval time.Duration
	mu             sync.RWMutex
	stopCh         chan struct{}
	logger         Logger
}

// Logger 日志接口
type Logger interface {
	Info(msg string, args ...interface{})
	Error(msg string, args ...interface{})
	Warn(msg string, args ...interface{})
}

// ModelConfig 模型配置
type ModelConfig struct {
	Models []ModelDefinition `json:"models"`
}

// ModelDefinition 模型定义
type ModelDefinition struct {
	ModelID       string                 `json:"model_id"`
	ModelName     string                 `json:"model_name"`
	Provider      string                 `json:"provider"`
	PricingTier   string                 `json:"pricing_tier"`
	ContextLength int                    `json:"context_length"`
	Capabilities  []string               `json:"capabilities"`
	Endpoint      string                 `json:"endpoint"`
	APIKey        string                 `json:"api_key"`
	Pricing       PricingDefinition      `json:"pricing"`
	Config        map[string]interface{} `json:"config"`
	Enabled       bool                   `json:"enabled"`
}

// PricingDefinition 定价定义
type PricingDefinition struct {
	InputPricePerMToken  float64 `json:"input_price_per_m_token"`
	OutputPricePerMToken float64 `json:"output_price_per_m_token"`
}

// NewDynamicModelLoader 创建动态模型加载器
func NewDynamicModelLoader(
	registry *domain.ModelRegistry,
	configPath string,
	reloadInterval time.Duration,
	logger Logger,
) *DynamicModelLoader {
	return &DynamicModelLoader{
		registry:       registry,
		configPath:     configPath,
		reloadInterval: reloadInterval,
		stopCh:         make(chan struct{}),
		logger:         logger,
	}
}

// Start 启动动态加载器
func (dl *DynamicModelLoader) Start(ctx context.Context) error {
	// 初始加载
	if err := dl.LoadModels(); err != nil {
		return fmt.Errorf("initial model load failed: %w", err)
	}

	// 启动定期重载
	go dl.reloadLoop(ctx)

	dl.logger.Info("Dynamic model loader started", "config_path", dl.configPath, "interval", dl.reloadInterval)

	return nil
}

// Stop 停止动态加载器
func (dl *DynamicModelLoader) Stop() {
	close(dl.stopCh)
	dl.logger.Info("Dynamic model loader stopped")
}

// LoadModels 加载模型配置
func (dl *DynamicModelLoader) LoadModels() error {
	dl.mu.Lock()
	defer dl.mu.Unlock()

	// 读取配置文件
	data, err := os.ReadFile(dl.configPath)
	if err != nil {
		return fmt.Errorf("failed to read config file: %w", err)
	}

	var config ModelConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return fmt.Errorf("failed to parse config: %w", err)
	}

	// 验证和加载模型
	loaded := 0
	failed := 0

	for _, modelDef := range config.Models {
		if !modelDef.Enabled {
			continue
		}

		modelInfo, err := dl.convertToModelInfo(&modelDef)
		if err != nil {
			dl.logger.Error("Failed to convert model definition", "model_id", modelDef.ModelID, "error", err)
			failed++
			continue
		}

		// 注册到 registry
		if err := dl.registry.Register(modelInfo); err != nil {
			dl.logger.Error("Failed to register model", "model_id", modelDef.ModelID, "error", err)
			failed++
			continue
		}

		loaded++
	}

	dl.logger.Info("Models loaded", "loaded", loaded, "failed", failed, "total", len(config.Models))

	return nil
}

// ReloadModels 重新加载模型（热重载）
func (dl *DynamicModelLoader) ReloadModels() error {
	dl.logger.Info("Reloading models from config")

	// 保存当前模型列表
	oldModels := dl.registry.ListAll()
	oldModelIDs := make(map[string]bool)
	for _, m := range oldModels {
		oldModelIDs[m.ModelID] = true
	}

	// 读取新配置
	data, err := os.ReadFile(dl.configPath)
	if err != nil {
		return fmt.Errorf("failed to read config file: %w", err)
	}

	var config ModelConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return fmt.Errorf("failed to parse config: %w", err)
	}

	// 加载新模型
	newModelIDs := make(map[string]bool)
	updated := 0
	added := 0

	for _, modelDef := range config.Models {
		newModelIDs[modelDef.ModelID] = true

		if !modelDef.Enabled {
			continue
		}

		modelInfo, err := dl.convertToModelInfo(&modelDef)
		if err != nil {
			dl.logger.Error("Failed to convert model definition", "model_id", modelDef.ModelID, "error", err)
			continue
		}

		// 检查是新增还是更新
		if oldModelIDs[modelDef.ModelID] {
			// 更新现有模型
			if err := dl.registry.Update(modelInfo); err != nil {
				dl.logger.Error("Failed to update model", "model_id", modelDef.ModelID, "error", err)
				continue
			}
			updated++
		} else {
			// 注册新模型
			if err := dl.registry.Register(modelInfo); err != nil {
				dl.logger.Error("Failed to register new model", "model_id", modelDef.ModelID, "error", err)
				continue
			}
			added++
		}
	}

	// 删除不再存在的模型
	removed := 0
	for modelID := range oldModelIDs {
		if !newModelIDs[modelID] {
			dl.registry.Unregister(modelID)
			removed++
		}
	}

	dl.logger.Info("Models reloaded", "added", added, "updated", updated, "removed", removed)

	return nil
}

// reloadLoop 重载循环
func (dl *DynamicModelLoader) reloadLoop(ctx context.Context) {
	ticker := time.NewTicker(dl.reloadInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-dl.stopCh:
			return
		case <-ticker.C:
			if err := dl.ReloadModels(); err != nil {
				dl.logger.Error("Failed to reload models", "error", err)
			}
		}
	}
}

// convertToModelInfo 转换模型定义为ModelInfo
func (dl *DynamicModelLoader) convertToModelInfo(def *ModelDefinition) (*domain.ModelInfo, error) {
	// 验证必需字段
	if def.ModelID == "" || def.ModelName == "" || def.Provider == "" {
		return nil, fmt.Errorf("missing required fields")
	}

	// 转换 Provider
	provider, err := dl.parseProvider(def.Provider)
	if err != nil {
		return nil, err
	}

	// 转换 PricingTier
	pricingTier, err := dl.parsePricingTier(def.PricingTier)
	if err != nil {
		return nil, err
	}

	// 转换 Capabilities
	capabilities := make([]domain.ModelCapability, 0)
	for _, cap := range def.Capabilities {
		capability, err := dl.parseCapability(cap)
		if err != nil {
			dl.logger.Warn("Unknown capability", "capability", cap)
			continue
		}
		capabilities = append(capabilities, capability)
	}

	// 创建 ModelInfo
	modelInfo := &domain.ModelInfo{
		ModelID:       def.ModelID,
		ModelName:     def.ModelName,
		Provider:      provider,
		PricingTier:   pricingTier,
		ContextLength: def.ContextLength,
		Capabilities:  capabilities,
		Endpoint:      def.Endpoint,
		APIKey:        def.APIKey,

		// 定价
		InputPricePerMToken:  def.Pricing.InputPricePerMToken,
		OutputPricePerMToken: def.Pricing.OutputPricePerMToken,

		// 默认值
		Availability: 1.0,
		ErrorRate:    0.0,
		AvgLatency:   100 * time.Millisecond,

		// 配置
		Config: def.Config,
	}

	return modelInfo, nil
}

// parseProvider 解析提供商
func (dl *DynamicModelLoader) parseProvider(provider string) (domain.ModelProvider, error) {
	switch provider {
	case "openai":
		return domain.ProviderOpenAI, nil
	case "anthropic":
		return domain.ProviderAnthropic, nil
	case "azure":
		return domain.ProviderAzure, nil
	case "google":
		return domain.ProviderGoogle, nil
	case "baidu":
		return domain.ProviderBaidu, nil
	case "alibaba":
		return domain.ProviderAlibaba, nil
	case "tencent":
		return domain.ProviderTencent, nil
	case "zhipu":
		return domain.ProviderZhipu, nil
	default:
		return "", fmt.Errorf("unknown provider: %s", provider)
	}
}

// parsePricingTier 解析定价层级
func (dl *DynamicModelLoader) parsePricingTier(tier string) (domain.PricingTier, error) {
	switch tier {
	case "free", "Free":
		return domain.TierFree, nil
	case "basic", "Basic":
		return domain.TierBasic, nil
	case "standard", "Standard":
		return domain.TierStandard, nil
	case "premium", "Premium":
		return domain.TierPremium, nil
	case "enterprise", "Enterprise":
		return domain.TierEnterprise, nil
	default:
		return domain.TierStandard, nil // 默认
	}
}

// parseCapability 解析能力
func (dl *DynamicModelLoader) parseCapability(cap string) (domain.ModelCapability, error) {
	switch cap {
	case "chat", "Chat":
		return domain.CapabilityChat, nil
	case "completion", "Completion":
		return domain.CapabilityCompletion, nil
	case "embedding", "Embedding":
		return domain.CapabilityEmbedding, nil
	case "function_calling", "FunctionCalling":
		return domain.CapabilityFunctionCalling, nil
	case "streaming", "Streaming":
		return domain.CapabilityStreaming, nil
	case "vision", "Vision":
		return domain.CapabilityVision, nil
	case "audio", "Audio":
		return domain.CapabilityAudio, nil
	default:
		return "", fmt.Errorf("unknown capability: %s", cap)
	}
}

// GetModelsConfig 获取当前模型配置
func (dl *DynamicModelLoader) GetModelsConfig() ([]ModelDefinition, error) {
	dl.mu.RLock()
	defer dl.mu.RUnlock()

	data, err := os.ReadFile(dl.configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var config ModelConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, fmt.Errorf("failed to parse config: %w", err)
	}

	return config.Models, nil
}

// AddModel 动态添加模型
func (dl *DynamicModelLoader) AddModel(def *ModelDefinition) error {
	dl.mu.Lock()
	defer dl.mu.Unlock()

	// 转换并注册
	modelInfo, err := dl.convertToModelInfo(def)
	if err != nil {
		return fmt.Errorf("failed to convert model: %w", err)
	}

	if err := dl.registry.Register(modelInfo); err != nil {
		return fmt.Errorf("failed to register model: %w", err)
	}

	// 更新配置文件
	if err := dl.appendToConfig(def); err != nil {
		dl.logger.Warn("Failed to update config file", "error", err)
	}

	dl.logger.Info("Model added dynamically", "model_id", def.ModelID)

	return nil
}

// RemoveModel 动态移除模型
func (dl *DynamicModelLoader) RemoveModel(modelID string) error {
	dl.mu.Lock()
	defer dl.mu.Unlock()

	// 从 registry 移除
	dl.registry.Unregister(modelID)

	// 更新配置文件
	if err := dl.removeFromConfig(modelID); err != nil {
		dl.logger.Warn("Failed to update config file", "error", err)
	}

	dl.logger.Info("Model removed dynamically", "model_id", modelID)

	return nil
}

// appendToConfig 追加到配置文件
func (dl *DynamicModelLoader) appendToConfig(def *ModelDefinition) error {
	data, err := os.ReadFile(dl.configPath)
	if err != nil {
		return err
	}

	var config ModelConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return err
	}

	config.Models = append(config.Models, *def)

	newData, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(dl.configPath, newData, 0644)
}

// removeFromConfig 从配置文件移除
func (dl *DynamicModelLoader) removeFromConfig(modelID string) error {
	data, err := os.ReadFile(dl.configPath)
	if err != nil {
		return err
	}

	var config ModelConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return err
	}

	// 过滤掉要删除的模型
	newModels := make([]ModelDefinition, 0)
	for _, m := range config.Models {
		if m.ModelID != modelID {
			newModels = append(newModels, m)
		}
	}
	config.Models = newModels

	newData, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(dl.configPath, newData, 0644)
}
