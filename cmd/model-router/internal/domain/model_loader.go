package domain

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// ModelConfigFile 模型配置文件结构
type ModelConfigFile struct {
	Models []ModelConfigYAML `yaml:"models"`
}

// ModelConfigYAML YAML 配置结构
type ModelConfigYAML struct {
	ID              string   `yaml:"id"`
	Name            string   `yaml:"name"`
	DisplayName     string   `yaml:"display_name"`
	Provider        string   `yaml:"provider"`
	Type            string   `yaml:"type"`
	Status          string   `yaml:"status"`
	Endpoint        string   `yaml:"endpoint"`
	APIKeyEnv       string   `yaml:"api_key_env"` // 从环境变量读取 API Key
	MaxTokens       int      `yaml:"max_tokens"`
	ContextWindow   int      `yaml:"context_window"`
	InputPricePerK  float64  `yaml:"input_price_per_k"`
	OutputPricePerK float64  `yaml:"output_price_per_k"`
	Priority        int      `yaml:"priority"`
	Weight          int      `yaml:"weight"`
	Timeout         int      `yaml:"timeout"` // 秒
	RetryCount      int      `yaml:"retry_count"`
	RateLimit       int      `yaml:"rate_limit"` // 请求/分钟
	Capabilities    []string `yaml:"capabilities"`
}

// LoadModelsFromFile 从配置文件加载模型
func LoadModelsFromFile(path string) ([]*ModelInfo, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read model config file: %w", err)
	}

	var configFile ModelConfigFile
	if err := yaml.Unmarshal(data, &configFile); err != nil {
		return nil, fmt.Errorf("failed to unmarshal model config: %w", err)
	}

	models := make([]*ModelInfo, 0, len(configFile.Models))
	for _, cfg := range configFile.Models {
		model, err := convertYAMLToModel(cfg)
		if err != nil {
			return nil, fmt.Errorf("failed to convert model %s: %w", cfg.ID, err)
		}
		models = append(models, model)
	}

	return models, nil
}

// convertYAMLToModel 将 YAML 配置转换为 ModelInfo
func convertYAMLToModel(cfg ModelConfigYAML) (*ModelInfo, error) {
	// 从环境变量读取 API Key
	apiKey := ""
	if cfg.APIKeyEnv != "" {
		apiKey = os.Getenv(cfg.APIKeyEnv)
	}

	// 转换 Provider
	provider := ModelProvider(cfg.Provider)
	if !isValidProvider(provider) {
		return nil, fmt.Errorf("invalid provider: %s", cfg.Provider)
	}

	// 转换状态
	status := cfg.Status
	if status == "" {
		status = "active"
	}

	// 转换能力
	capabilities := make([]ModelCapability, 0, len(cfg.Capabilities))
	for _, cap := range cfg.Capabilities {
		capability := ModelCapability(cap)
		if isValidCapability(capability) {
			capabilities = append(capabilities, capability)
		}
	}

	model := &ModelInfo{
		ModelID:         cfg.ID,
		ModelName:       cfg.Name,
		DisplayName:     cfg.DisplayName,
		Provider:        provider,
		Capabilities:    capabilities,
		ContextLength:   cfg.ContextWindow,
		MaxOutputTokens: cfg.MaxTokens,
		InputPrice:      cfg.InputPricePerK,
		OutputPrice:     cfg.OutputPricePerK,

		// 初始化健康状态
		AvgLatency:   100 * time.Millisecond, // 默认延迟
		Availability: 1.0,                    // 默认 100% 可用
		Available:    status == "active",
		ErrorRate:    0.0, // 默认无错误
		Enabled:      status == "active",

		UpdatedAt: time.Now(),
	}

	return model, nil
}

// isValidProvider 检查 Provider 是否有效
func isValidProvider(provider ModelProvider) bool {
	validProviders := []ModelProvider{
		ModelProviderOpenAI,
		ModelProviderAnthropic,
		ModelProviderGoogle,
		ModelProviderCohere,
		ModelProviderHuggingFace,
		ModelProviderLocal,
	}

	for _, p := range validProviders {
		if provider == p {
			return true
		}
	}
	return false
}

// isValidCapability 检查能力是否有效
func isValidCapability(cap ModelCapability) bool {
	validCapabilities := []ModelCapability{
		CapabilityChat,
		CapabilityStreaming,
		CapabilityFunction, // 对应 function_calling
		CapabilityVision,
		CapabilityEmbedding,
	}

	// 特殊处理别名
	if cap == "function_calling" {
		return true
	}
	if cap == "long_context" {
		return true
	}

	for _, c := range validCapabilities {
		if cap == c {
			return true
		}
	}
	return false
}
