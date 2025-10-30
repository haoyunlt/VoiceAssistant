package biz

import (
	"context"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// MockModelClient Mock的LLM客户端（用于测试）
type MockModelClient struct{}

// Call Mock实现
func (m *MockModelClient) Call(ctx context.Context, messages []ModelMessage, options map[string]interface{}) (string, error) {
	// 简单的规则判断
	userMessage := ""
	for _, msg := range messages {
		if msg.Role == "user" {
			userMessage = msg.Content
		}
	}

	// 根据关键词返回不同的意图
	response := `{
		"intent_type": "chat",
		"confidence": 0.8,
		"reason": "general conversation",
		"entities": {},
		"alternatives": []
	}`

	// 简单的关键词判断
	if contains(userMessage, "什么是") || contains(userMessage, "查询") {
		response = `{
			"intent_type": "rag",
			"confidence": 0.9,
			"reason": "knowledge query detected",
			"entities": {},
			"alternatives": [
				{"type": "chat", "confidence": 0.3, "reason": "could be general chat"}
			]
		}`
	} else if contains(userMessage, "帮我") || contains(userMessage, "执行") {
		response = `{
			"intent_type": "agent",
			"confidence": 0.85,
			"reason": "task execution requested",
			"entities": {},
			"alternatives": []
		}`
	}

	return response, nil
}

func contains(s, substr string) bool {
	return len(s) > 0 && len(substr) > 0 &&
		len(s) >= len(substr) &&
		findSubstring(s, substr)
}

func findSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// SetupIntentRecognition 设置意图识别（示例）
func SetupIntentRecognition(logger log.Logger) *IntentService {
	// 1. 创建缓存
	cache := NewMemoryIntentCache(10000)

	// 2. 创建识别器
	recognizers := []domain.IntentRecognizer{
		// 基于规则的识别器
		NewRuleBasedRecognizer(logger),

		// 基于LLM的识别器（使用Mock客户端）
		NewLLMBasedRecognizer(&MockModelClient{}, cache, logger),
	}

	// 3. 创建意图服务
	config := &IntentServiceConfig{
		UseCache:      true,
		UseFallback:   true,
		MinConfidence: domain.ConfidenceMedium,
	}

	intentService := NewIntentService(recognizers, cache, config, logger)

	return intentService
}

// ExampleUsage 使用示例
func ExampleUsage(logger log.Logger) {
	// 设置意图识别服务
	intentService := SetupIntentRecognition(logger)

	// 创建意图识别输入
	input := &domain.IntentInput{
		Message:        "什么是人工智能？",
		ConversationID: "conv_123",
		UserID:         "user_456",
		TenantID:       "tenant_789",
		History:        []domain.Message{},
		Context:        make(map[string]interface{}),
		Params:         make(map[string]interface{}),
	}

	// 识别意图
	ctx := context.Background()
	intent, err := intentService.RecognizeIntent(ctx, input)
	if err != nil {
		log.NewHelper(logger).Errorf("Intent recognition failed: %v", err)
		return
	}

	log.NewHelper(logger).Infof(
		"Recognized intent: type=%s, confidence=%.2f, reason=%s",
		intent.Type,
		intent.Confidence,
		intent.Reason,
	)

	// 根据意图执行不同的逻辑
	switch intent.Type {
	case domain.IntentTypeRAG:
		log.NewHelper(logger).Info("Routing to RAG pipeline...")
	case domain.IntentTypeAgent:
		log.NewHelper(logger).Info("Routing to Agent pipeline...")
	case domain.IntentTypeChat:
		log.NewHelper(logger).Info("Routing to Chat pipeline...")
	default:
		log.NewHelper(logger).Warn("Unknown intent type")
	}
}
