package domain

import (
	"time"

	"github.com/google/uuid"
)

// ModelProvider 模型提供商
type ModelProvider string

const (
	ModelProviderOpenAI      ModelProvider = "openai"      // OpenAI
	ModelProviderAnthropic   ModelProvider = "anthropic"   // Anthropic (Claude)
	ModelProviderGoogle      ModelProvider = "google"      // Google (Gemini)
	ModelProviderCohere      ModelProvider = "cohere"      // Cohere
	ModelProviderHuggingFace ModelProvider = "huggingface" // HuggingFace
	ModelProviderLocal       ModelProvider = "local"       // 本地部署
)

// ModelType 模型类型
type ModelType string

const (
	ModelTypeChat       ModelType = "chat"       // 对话模型
	ModelTypeEmbedding  ModelType = "embedding"  // 向量模型
	ModelTypeCompletion ModelType = "completion" // 补全模型
	ModelTypeImage      ModelType = "image"      // 图像模型
)

// ModelStatus 模型状态
type ModelStatus string

const (
	ModelStatusActive      ModelStatus = "active"      // 激活
	ModelStatusInactive    ModelStatus = "inactive"    // 未激活
	ModelStatusMaintenance ModelStatus = "maintenance" // 维护中
	ModelStatusDeprecated  ModelStatus = "deprecated"  // 已废弃
)

// Model 模型聚合根
type Model struct {
	ID              string
	Name            string
	DisplayName     string
	Provider        ModelProvider
	Type            ModelType
	Status          ModelStatus
	Endpoint        string   // API端点
	APIKey          string   // API密钥
	MaxTokens       int      // 最大Token数
	ContextWindow   int      // 上下文窗口
	InputPricePerK  float64  // 输入价格(每1K tokens, USD)
	OutputPricePerK float64  // 输出价格(每1K tokens, USD)
	Priority        int      // 优先级：0-100
	Weight          int      // 权重（负载均衡）
	Timeout         int      // 超时时间(秒)
	RetryCount      int      // 重试次数
	RateLimit       int      // 限流（请求/分钟）
	Capabilities    []string // 能力列表
	Metadata        map[string]interface{}
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// NewModel 创建新模型
func NewModel(
	name, displayName string,
	provider ModelProvider,
	modelType ModelType,
	endpoint, apiKey string,
) *Model {
	id := "model_" + uuid.New().String()
	now := time.Now()

	return &Model{
		ID:            id,
		Name:          name,
		DisplayName:   displayName,
		Provider:      provider,
		Type:          modelType,
		Status:        ModelStatusActive,
		Endpoint:      endpoint,
		APIKey:        apiKey,
		MaxTokens:     4096,
		ContextWindow: 8192,
		Priority:      50,
		Weight:        100,
		Timeout:       30,
		RetryCount:    3,
		RateLimit:     60,
		Capabilities:  make([]string, 0),
		Metadata:      make(map[string]interface{}),
		CreatedAt:     now,
		UpdatedAt:     now,
	}
}

// Update 更新模型信息
func (m *Model) Update(displayName, endpoint string) {
	if displayName != "" {
		m.DisplayName = displayName
	}
	if endpoint != "" {
		m.Endpoint = endpoint
	}
	m.UpdatedAt = time.Now()
}

// UpdatePricing 更新定价
func (m *Model) UpdatePricing(inputPrice, outputPrice float64) {
	m.InputPricePerK = inputPrice
	m.OutputPricePerK = outputPrice
	m.UpdatedAt = time.Now()
}

// SetPriority 设置优先级
func (m *Model) SetPriority(priority int) error {
	if priority < 0 || priority > 100 {
		return ErrInvalidPriority
	}
	m.Priority = priority
	m.UpdatedAt = time.Now()
	return nil
}

// SetWeight 设置权重
func (m *Model) SetWeight(weight int) error {
	if weight < 0 || weight > 1000 {
		return ErrInvalidWeight
	}
	m.Weight = weight
	m.UpdatedAt = time.Now()
	return nil
}

// SetRateLimit 设置限流
func (m *Model) SetRateLimit(limit int) error {
	if limit < 0 {
		return ErrInvalidRateLimit
	}
	m.RateLimit = limit
	m.UpdatedAt = time.Now()
	return nil
}

// Activate 激活模型
func (m *Model) Activate() {
	m.Status = ModelStatusActive
	m.UpdatedAt = time.Now()
}

// Deactivate 停用模型
func (m *Model) Deactivate() {
	m.Status = ModelStatusInactive
	m.UpdatedAt = time.Now()
}

// SetMaintenance 设置维护模式
func (m *Model) SetMaintenance() {
	m.Status = ModelStatusMaintenance
	m.UpdatedAt = time.Now()
}

// Deprecate 废弃模型
func (m *Model) Deprecate() {
	m.Status = ModelStatusDeprecated
	m.UpdatedAt = time.Now()
}

// IsAvailable 检查是否可用
func (m *Model) IsAvailable() bool {
	return m.Status == ModelStatusActive
}

// CalculateCost 计算成本
func (m *Model) CalculateCost(inputTokens, outputTokens int) float64 {
	inputCost := float64(inputTokens) / 1000.0 * m.InputPricePerK
	outputCost := float64(outputTokens) / 1000.0 * m.OutputPricePerK
	return inputCost + outputCost
}

// AddCapability 添加能力
func (m *Model) AddCapability(capability string) {
	for _, c := range m.Capabilities {
		if c == capability {
			return // 已存在
		}
	}
	m.Capabilities = append(m.Capabilities, capability)
	m.UpdatedAt = time.Now()
}

// HasCapability 检查是否具备能力
func (m *Model) HasCapability(capability string) bool {
	for _, c := range m.Capabilities {
		if c == capability {
			return true
		}
	}
	return false
}

// UpdateMetadata 更新元数据
func (m *Model) UpdateMetadata(key string, value interface{}) {
	if m.Metadata == nil {
		m.Metadata = make(map[string]interface{})
	}
	m.Metadata[key] = value
	m.UpdatedAt = time.Now()
}

// Validate 验证模型
func (m *Model) Validate() error {
	if m.Name == "" {
		return ErrInvalidModelName
	}
	if m.Endpoint == "" {
		return ErrInvalidEndpoint
	}
	if m.MaxTokens <= 0 {
		return ErrInvalidMaxTokens
	}
	return nil
}
