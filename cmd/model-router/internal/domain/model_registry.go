package domain

import (
	"fmt"
	"sync"
	"time"
)

// ModelCapability 模型能力枚举
type ModelCapability string

const (
	CapabilityChat      ModelCapability = "chat"
	CapabilityEmbedding ModelCapability = "embedding"
	CapabilityVision    ModelCapability = "vision"
	CapabilityFunction  ModelCapability = "function_calling"
	CapabilityStreaming ModelCapability = "streaming"
)

// ModelProvider 模型提供商
type ModelProvider string

const (
	ProviderOpenAI ModelProvider = "openai"
	ProviderClaude ModelProvider = "claude"
	ProviderZhipu  ModelProvider = "zhipu"
)

// ModelInfo 模型信息
type ModelInfo struct {
	// 基本信息
	ModelID     string        `json:"model_id"`     // 模型唯一标识
	Provider    ModelProvider `json:"provider"`     // 提供商
	ModelName   string        `json:"model_name"`   // 模型名称 (如 gpt-3.5-turbo)
	DisplayName string        `json:"display_name"` // 显示名称
	Description string        `json:"description"`  // 描述

	// 能力
	Capabilities    []ModelCapability `json:"capabilities"`      // 支持的能力
	ContextLength   int               `json:"context_length"`    // 上下文长度
	MaxOutputTokens int               `json:"max_output_tokens"` // 最大输出token数

	// 定价 (单位: USD per 1K tokens)
	InputPrice  float64 `json:"input_price"`  // 输入价格
	OutputPrice float64 `json:"output_price"` // 输出价格

	// 性能指标
	AvgLatency   time.Duration `json:"avg_latency"`  // 平均延迟
	ErrorRate    float64       `json:"error_rate"`   // 错误率
	Availability float64       `json:"availability"` // 可用性 (0-1)

	// 状态
	Enabled   bool      `json:"enabled"`    // 是否启用
	UpdatedAt time.Time `json:"updated_at"` // 更新时间
}

// HasCapability 检查是否具有某项能力
func (m *ModelInfo) HasCapability(cap ModelCapability) bool {
	for _, c := range m.Capabilities {
		if c == cap {
			return true
		}
	}
	return false
}

// EstimateCost 估算成本
func (m *ModelInfo) EstimateCost(inputTokens, outputTokens int) float64 {
	inputCost := float64(inputTokens) / 1000.0 * m.InputPrice
	outputCost := float64(outputTokens) / 1000.0 * m.OutputPrice
	return inputCost + outputCost
}

// IsHealthy 检查模型是否健康
func (m *ModelInfo) IsHealthy() bool {
	return m.Enabled && m.Availability > 0.95 && m.ErrorRate < 0.05
}

// ModelRegistry 模型注册表
type ModelRegistry struct {
	models map[string]*ModelInfo // model_id -> ModelInfo
	mu     sync.RWMutex
}

// NewModelRegistry 创建模型注册表
func NewModelRegistry() *ModelRegistry {
	registry := &ModelRegistry{
		models: make(map[string]*ModelInfo),
	}

	// 初始化默认模型
	registry.initDefaultModels()

	return registry
}

// initDefaultModels 初始化默认模型
func (r *ModelRegistry) initDefaultModels() {
	defaultModels := []*ModelInfo{
		// OpenAI GPT-3.5
		{
			ModelID:         "openai-gpt-3.5-turbo",
			Provider:        ProviderOpenAI,
			ModelName:       "gpt-3.5-turbo",
			DisplayName:     "GPT-3.5 Turbo",
			Description:     "Fast and cost-effective model for most tasks",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityFunction, CapabilityStreaming},
			ContextLength:   4096,
			MaxOutputTokens: 4096,
			InputPrice:      0.0005, // $0.0005 per 1K tokens
			OutputPrice:     0.0015, // $0.0015 per 1K tokens
			AvgLatency:      500 * time.Millisecond,
			ErrorRate:       0.01,
			Availability:    0.99,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},

		// OpenAI GPT-3.5-16k
		{
			ModelID:         "openai-gpt-3.5-turbo-16k",
			Provider:        ProviderOpenAI,
			ModelName:       "gpt-3.5-turbo-16k",
			DisplayName:     "GPT-3.5 Turbo 16K",
			Description:     "Extended context window version",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityFunction, CapabilityStreaming},
			ContextLength:   16384,
			MaxOutputTokens: 4096,
			InputPrice:      0.003,
			OutputPrice:     0.004,
			AvgLatency:      600 * time.Millisecond,
			ErrorRate:       0.01,
			Availability:    0.99,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},

		// OpenAI GPT-4
		{
			ModelID:         "openai-gpt-4",
			Provider:        ProviderOpenAI,
			ModelName:       "gpt-4",
			DisplayName:     "GPT-4",
			Description:     "Most capable model for complex tasks",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityFunction, CapabilityStreaming, CapabilityVision},
			ContextLength:   8192,
			MaxOutputTokens: 4096,
			InputPrice:      0.03,
			OutputPrice:     0.06,
			AvgLatency:      1500 * time.Millisecond,
			ErrorRate:       0.005,
			Availability:    0.98,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},

		// Claude 3 Sonnet
		{
			ModelID:         "claude-3-sonnet",
			Provider:        ProviderClaude,
			ModelName:       "claude-3-sonnet-20240229",
			DisplayName:     "Claude 3 Sonnet",
			Description:     "Balanced performance and speed",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityVision, CapabilityStreaming},
			ContextLength:   200000,
			MaxOutputTokens: 4096,
			InputPrice:      0.003,
			OutputPrice:     0.015,
			AvgLatency:      800 * time.Millisecond,
			ErrorRate:       0.008,
			Availability:    0.99,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},

		// Claude 3 Opus
		{
			ModelID:         "claude-3-opus",
			Provider:        ProviderClaude,
			ModelName:       "claude-3-opus-20240229",
			DisplayName:     "Claude 3 Opus",
			Description:     "Most intelligent model for complex tasks",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityVision, CapabilityStreaming},
			ContextLength:   200000,
			MaxOutputTokens: 4096,
			InputPrice:      0.015,
			OutputPrice:     0.075,
			AvgLatency:      2000 * time.Millisecond,
			ErrorRate:       0.005,
			Availability:    0.98,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},

		// 智谱 GLM-4
		{
			ModelID:         "zhipu-glm-4",
			Provider:        ProviderZhipu,
			ModelName:       "glm-4",
			DisplayName:     "GLM-4",
			Description:     "中文优化的大模型",
			Capabilities:    []ModelCapability{CapabilityChat, CapabilityFunction, CapabilityStreaming},
			ContextLength:   128000,
			MaxOutputTokens: 4096,
			InputPrice:      0.001,
			OutputPrice:     0.001,
			AvgLatency:      700 * time.Millisecond,
			ErrorRate:       0.01,
			Availability:    0.99,
			Enabled:         true,
			UpdatedAt:       time.Now(),
		},
	}

	for _, model := range defaultModels {
		r.models[model.ModelID] = model
	}
}

// Register 注册模型
func (r *ModelRegistry) Register(model *ModelInfo) error {
	if model.ModelID == "" {
		return fmt.Errorf("model_id is required")
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	model.UpdatedAt = time.Now()
	r.models[model.ModelID] = model

	return nil
}

// Get 获取模型信息
func (r *ModelRegistry) Get(modelID string) (*ModelInfo, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	model, exists := r.models[modelID]
	if !exists {
		return nil, fmt.Errorf("model not found: %s", modelID)
	}

	return model, nil
}

// GetByProvider 获取指定提供商的所有模型
func (r *ModelRegistry) GetByProvider(provider ModelProvider) []*ModelInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var models []*ModelInfo
	for _, model := range r.models {
		if model.Provider == provider && model.Enabled {
			models = append(models, model)
		}
	}

	return models
}

// GetByCapability 获取具有指定能力的所有模型
func (r *ModelRegistry) GetByCapability(capability ModelCapability) []*ModelInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var models []*ModelInfo
	for _, model := range r.models {
		if model.HasCapability(capability) && model.Enabled {
			models = append(models, model)
		}
	}

	return models
}

// ListAll 列出所有模型
func (r *ModelRegistry) ListAll() []*ModelInfo {
	r.mu.RLock()
	defer r.mu.RUnlock()

	models := make([]*ModelInfo, 0, len(r.models))
	for _, model := range r.models {
		if model.Enabled {
			models = append(models, model)
		}
	}

	return models
}

// UpdateMetrics 更新模型性能指标
func (r *ModelRegistry) UpdateMetrics(modelID string, latency time.Duration, success bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	model, exists := r.models[modelID]
	if !exists {
		return fmt.Errorf("model not found: %s", modelID)
	}

	// 使用指数移动平均更新延迟
	alpha := 0.2
	model.AvgLatency = time.Duration(float64(model.AvgLatency)*(1-alpha) + float64(latency)*alpha)

	// 更新错误率 (简单计数，实际应使用滑动窗口)
	if !success {
		model.ErrorRate = model.ErrorRate*0.95 + 0.05
	} else {
		model.ErrorRate = model.ErrorRate * 0.99
	}

	// 更新可用性
	if success {
		model.Availability = model.Availability*0.99 + 0.01
	} else {
		model.Availability = model.Availability * 0.95
	}

	model.UpdatedAt = time.Now()

	return nil
}

// Disable 禁用模型
func (r *ModelRegistry) Disable(modelID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	model, exists := r.models[modelID]
	if !exists {
		return fmt.Errorf("model not found: %s", modelID)
	}

	model.Enabled = false
	model.UpdatedAt = time.Now()

	return nil
}

// Enable 启用模型
func (r *ModelRegistry) Enable(modelID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	model, exists := r.models[modelID]
	if !exists {
		return fmt.Errorf("model not found: %s", modelID)
	}

	model.Enabled = true
	model.UpdatedAt = time.Now()

	return nil
}
