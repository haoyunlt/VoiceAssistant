package domain

import (
	"time"
)

// IntentType 意图类型
type IntentType string

const (
	IntentTypeChat       IntentType = "chat"        // 普通对话
	IntentTypeRAG        IntentType = "rag"         // 知识检索问答
	IntentTypeAgent      IntentType = "agent"       // 任务型对话（需要工具）
	IntentTypeVoice      IntentType = "voice"       // 语音处理
	IntentTypeMultimodal IntentType = "multimodal"  // 多模态处理
	IntentTypeUnknown    IntentType = "unknown"     // 未知意图
)

// IntentConfidence 意图置信度
type IntentConfidence float64

const (
	ConfidenceVeryLow  IntentConfidence = 0.3
	ConfidenceLow      IntentConfidence = 0.5
	ConfidenceMedium   IntentConfidence = 0.7
	ConfidenceHigh     IntentConfidence = 0.85
	ConfidenceVeryHigh IntentConfidence = 0.95
)

// Intent 意图识别结果
type Intent struct {
	Type       IntentType                 // 主要意图类型
	Confidence IntentConfidence           // 置信度 (0-1)
	Entities   map[string]interface{}     // 提取的实体
	Slots      map[string]interface{}     // 槽位信息
	Metadata   map[string]interface{}     // 元数据
	Reason     string                     // 识别理由
	Timestamp  time.Time                  // 识别时间

	// 多意图支持
	AlternativeIntents []*AlternativeIntent // 备选意图
}

// AlternativeIntent 备选意图
type AlternativeIntent struct {
	Type       IntentType       // 意图类型
	Confidence IntentConfidence // 置信度
	Reason     string           // 理由
}

// IntentRecognizer 意图识别器接口
type IntentRecognizer interface {
	// Recognize 识别意图
	Recognize(input *IntentInput) (*Intent, error)

	// Name 识别器名称
	Name() string

	// Priority 优先级（数字越小优先级越高）
	Priority() int
}

// IntentInput 意图识别输入
type IntentInput struct {
	Message        string                 // 用户消息
	ConversationID string                 // 对话ID
	UserID         string                 // 用户ID
	TenantID       string                 // 租户ID
	History        []Message              // 对话历史
	Context        map[string]interface{} // 上下文信息
	Params         map[string]interface{} // 额外参数
}

// Message 历史消息
type Message struct {
	Role    string // user/assistant/system
	Content string // 消息内容
}

// NewIntent 创建意图
func NewIntent(intentType IntentType, confidence IntentConfidence) *Intent {
	return &Intent{
		Type:       intentType,
		Confidence: confidence,
		Entities:   make(map[string]interface{}),
		Slots:      make(map[string]interface{}),
		Metadata:   make(map[string]interface{}),
		Timestamp:  time.Now(),
		AlternativeIntents: make([]*AlternativeIntent, 0),
	}
}

// AddAlternative 添加备选意图
func (i *Intent) AddAlternative(intentType IntentType, confidence IntentConfidence, reason string) {
	i.AlternativeIntents = append(i.AlternativeIntents, &AlternativeIntent{
		Type:       intentType,
		Confidence: confidence,
		Reason:     reason,
	})
}

// IsHighConfidence 是否高置信度
func (i *Intent) IsHighConfidence() bool {
	return i.Confidence >= ConfidenceHigh
}

// IsMediumConfidence 是否中等置信度
func (i *Intent) IsMediumConfidence() bool {
	return i.Confidence >= ConfidenceMedium && i.Confidence < ConfidenceHigh
}

// IsLowConfidence 是否低置信度
func (i *Intent) IsLowConfidence() bool {
	return i.Confidence < ConfidenceMedium
}

// ShouldFallback 是否应该降级
func (i *Intent) ShouldFallback() bool {
	return i.Type == IntentTypeUnknown || i.Confidence < ConfidenceLow
}

// IntentCache 意图缓存接口
type IntentCache interface {
	// Get 获取缓存的意图
	Get(key string) (*Intent, bool)

	// Set 设置缓存
	Set(key string, intent *Intent, ttl time.Duration)

	// Delete 删除缓存
	Delete(key string)

	// Clear 清空缓存
	Clear()
}
