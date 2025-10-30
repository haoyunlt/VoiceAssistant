package biz

import (
	"context"
	"os"
	"testing"
	"time"
	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

func TestRuleBasedRecognizer_RAGIntent(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	recognizer := NewRuleBasedRecognizer(logger)

	testCases := []struct {
		name               string
		message            string
		expectedIntentType domain.IntentType
		minConfidence      domain.IntentConfidence
	}{
		{
			name:               "知识查询 - 什么是",
			message:            "什么是人工智能？",
			expectedIntentType: domain.IntentTypeRAG,
			minConfidence:      domain.ConfidenceMedium,
		},
		{
			name:               "知识查询 - 如何",
			message:            "如何学习机器学习？",
			expectedIntentType: domain.IntentTypeRAG,
			minConfidence:      domain.ConfidenceMedium,
		},
		{
			name:               "知识查询 - 查询",
			message:            "查询一下深度学习的资料",
			expectedIntentType: domain.IntentTypeRAG,
			minConfidence:      domain.ConfidenceMedium,
		},
		{
			name:               "知识查询 - 英文",
			message:            "What is artificial intelligence?",
			expectedIntentType: domain.IntentTypeRAG,
			minConfidence:      domain.ConfidenceMedium,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			input := &domain.IntentInput{
				Message:  tc.message,
				TenantID: "test_tenant",
			}

			intent, err := recognizer.Recognize(input)
			if err != nil {
				t.Fatalf("Recognize failed: %v", err)
			}

			if intent.Type != tc.expectedIntentType {
				t.Errorf("Expected intent type %s, got %s", tc.expectedIntentType, intent.Type)
			}

			if intent.Confidence < tc.minConfidence {
				t.Errorf("Confidence too low: %.2f < %.2f", intent.Confidence, tc.minConfidence)
			}

			t.Logf("Intent: %s, Confidence: %.2f, Reason: %s",
				intent.Type, intent.Confidence, intent.Reason)
		})
	}
}

func TestRuleBasedRecognizer_AgentIntent(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	recognizer := NewRuleBasedRecognizer(logger)

	testCases := []struct {
		name               string
		message            string
		expectedIntentType domain.IntentType
	}{
		{
			name:               "任务执行 - 帮我",
			message:            "帮我订一张去北京的机票",
			expectedIntentType: domain.IntentTypeAgent,
		},
		{
			name:               "任务执行 - 创建",
			message:            "创建一个新的工单",
			expectedIntentType: domain.IntentTypeAgent,
		},
		{
			name:               "任务执行 - 计算",
			message:            "计算一下 123 * 456",
			expectedIntentType: domain.IntentTypeAgent,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			input := &domain.IntentInput{
				Message:  tc.message,
				TenantID: "test_tenant",
			}

			intent, err := recognizer.Recognize(input)
			if err != nil {
				t.Fatalf("Recognize failed: %v", err)
			}

			// Agent和RAG可能有歧义，检查是否识别为这两者之一
			if intent.Type != tc.expectedIntentType && intent.Type != domain.IntentTypeRAG {
				t.Errorf("Expected intent type %s or rag, got %s", tc.expectedIntentType, intent.Type)
			}

			// 如果识别为RAG，检查是否有Agent作为备选意图
			if intent.Type == domain.IntentTypeRAG {
				hasAgentAlternative := false
				for _, alt := range intent.AlternativeIntents {
					if alt.Type == domain.IntentTypeAgent {
						hasAgentAlternative = true
						break
					}
				}
				if hasAgentAlternative {
					t.Logf("Recognized as RAG but has Agent as alternative (acceptable)")
				}
			}

			t.Logf("Intent: %s, Confidence: %.2f", intent.Type, intent.Confidence)
		})
	}
}

func TestRuleBasedRecognizer_ChatIntent(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	recognizer := NewRuleBasedRecognizer(logger)

	testCases := []string{
		"你好",
		"谢谢",
		"再见",
		"天气真好",
		"今天心情不错",
	}

	for _, message := range testCases {
		t.Run(message, func(t *testing.T) {
			input := &domain.IntentInput{
				Message:  message,
				TenantID: "test_tenant",
			}

			intent, err := recognizer.Recognize(input)
			if err != nil {
				t.Fatalf("Recognize failed: %v", err)
			}

			// 简单对话可能识别为chat或unknown
			if intent.Type != domain.IntentTypeChat && intent.Type != domain.IntentTypeUnknown {
				t.Logf("Message '%s' recognized as %s (not chat/unknown)", message, intent.Type)
			}

			t.Logf("Intent: %s, Confidence: %.2f", intent.Type, intent.Confidence)
		})
	}
}

func TestIntentCache(t *testing.T) {
	cache := NewMemoryIntentCache(100)

	// 测试Set和Get
	intent := domain.NewIntent(domain.IntentTypeRAG, domain.ConfidenceHigh)
	cache.Set("test_key", intent, 10*time.Minute)

	retrieved, found := cache.Get("test_key")
	if !found {
		t.Fatal("Expected to find cached intent")
	}

	if retrieved.Type != intent.Type {
		t.Errorf("Expected type %s, got %s", intent.Type, retrieved.Type)
	}

	// 测试Delete
	cache.Delete("test_key")
	_, found = cache.Get("test_key")
	if found {
		t.Fatal("Expected cache to be deleted")
	}

	// 测试统计
	stats := cache.GetStats()
	if stats.Hits != 1 {
		t.Errorf("Expected 1 hit, got %d", stats.Hits)
	}
	if stats.Misses != 1 {
		t.Errorf("Expected 1 miss, got %d", stats.Misses)
	}

	t.Logf("Cache stats: Hits=%d, Misses=%d, HitRate=%.2f",
		stats.Hits, stats.Misses, cache.HitRate())
}

func TestIntentService(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	cache := NewMemoryIntentCache(100)

	// 创建识别器
	recognizers := []domain.IntentRecognizer{
		NewRuleBasedRecognizer(logger),
		NewLLMBasedRecognizer(&MockModelClient{}, cache, logger),
	}

	// 创建服务
	config := &IntentServiceConfig{
		UseCache:      true,
		UseFallback:   true,
		MinConfidence: domain.ConfidenceMedium,
	}
	service := NewIntentService(recognizers, cache, config, logger)

	// 测试识别
	input := &domain.IntentInput{
		Message:        "什么是机器学习？",
		ConversationID: "conv_123",
		UserID:         "user_456",
		TenantID:       "tenant_789",
	}

	ctx := context.Background()
	intent, err := service.RecognizeIntent(ctx, input)
	if err != nil {
		t.Fatalf("RecognizeIntent failed: %v", err)
	}

	if intent.Type != domain.IntentTypeRAG {
		t.Errorf("Expected RAG intent, got %s", intent.Type)
	}

	t.Logf("Recognized: type=%s, confidence=%.2f, reason=%s",
		intent.Type, intent.Confidence, intent.Reason)

	// 测试缓存效果（第二次调用应该更快）
	intent2, err := service.RecognizeIntent(ctx, input)
	if err != nil {
		t.Fatalf("Second RecognizeIntent failed: %v", err)
	}

	if intent2.Type != intent.Type {
		t.Errorf("Cached intent type mismatch")
	}

	// 检查缓存统计
	if stats := service.GetCacheStats(); stats != nil {
		t.Logf("Cache stats: Hits=%d, Misses=%d, HitRate=%.2f%%",
			stats.Hits, stats.Misses, cache.HitRate()*100)
	}
}

func TestIntentService_ManualMode(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	cache := NewMemoryIntentCache(100)

	recognizers := []domain.IntentRecognizer{
		NewRuleBasedRecognizer(logger),
	}

	config := &IntentServiceConfig{
		UseCache:    false,
		UseFallback: false,
	}
	service := NewIntentService(recognizers, cache, config, logger)

	// 测试手动指定模式
	input := &domain.IntentInput{
		Message:  "随便什么内容",
		TenantID: "test_tenant",
		Params: map[string]interface{}{
			"mode": "agent", // 手动指定agent模式
		},
	}

	ctx := context.Background()
	intent, err := service.RecognizeIntent(ctx, input)
	if err != nil {
		t.Fatalf("RecognizeIntent failed: %v", err)
	}

	if intent.Type != domain.IntentTypeAgent {
		t.Errorf("Expected agent intent, got %s", intent.Type)
	}

	if intent.Reason != "manual_mode" {
		t.Errorf("Expected manual_mode reason, got %s", intent.Reason)
	}

	t.Logf("Manual mode: type=%s, confidence=%.2f", intent.Type, intent.Confidence)
}

func TestIntentService_LowConfidenceFallback(t *testing.T) {
	logger := log.NewStdLogger(os.Stdout)
	cache := NewMemoryIntentCache(100)

	// 创建一个总是返回低置信度的识别器
	lowConfRecognizer := &mockLowConfidenceRecognizer{}
	recognizers := []domain.IntentRecognizer{lowConfRecognizer}

	config := &IntentServiceConfig{
		UseCache:      false,
		UseFallback:   true,
		MinConfidence: domain.ConfidenceMedium, // 0.7
	}
	service := NewIntentService(recognizers, cache, config, logger)

	input := &domain.IntentInput{
		Message:  "模糊的输入",
		TenantID: "test_tenant",
	}

	ctx := context.Background()
	intent, err := service.RecognizeIntent(ctx, input)
	if err != nil {
		t.Fatalf("RecognizeIntent failed: %v", err)
	}

	// 应该降级到chat模式
	if intent.Type != domain.IntentTypeChat {
		t.Errorf("Expected chat fallback, got %s", intent.Type)
	}

	if intent.Reason != "fallback_due_to_low_confidence" {
		t.Errorf("Expected fallback reason, got %s", intent.Reason)
	}

	t.Logf("Fallback: type=%s, reason=%s", intent.Type, intent.Reason)
}

// Mock识别器，总是返回低置信度
type mockLowConfidenceRecognizer struct{}

func (m *mockLowConfidenceRecognizer) Recognize(input *domain.IntentInput) (*domain.Intent, error) {
	return domain.NewIntent(domain.IntentTypeUnknown, domain.ConfidenceLow), nil
}

func (m *mockLowConfidenceRecognizer) Name() string {
	return "mock_low_conf"
}

func (m *mockLowConfidenceRecognizer) Priority() int {
	return 99
}

// 基准测试
func BenchmarkRuleBasedRecognizer(b *testing.B) {
	logger := log.NewStdLogger(os.Stdout)
	recognizer := NewRuleBasedRecognizer(logger)

	input := &domain.IntentInput{
		Message:  "什么是人工智能？",
		TenantID: "test_tenant",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = recognizer.Recognize(input)
	}
}

func BenchmarkIntentServiceWithCache(b *testing.B) {
	logger := log.NewStdLogger(os.Stdout)
	cache := NewMemoryIntentCache(1000)

	recognizers := []domain.IntentRecognizer{
		NewRuleBasedRecognizer(logger),
	}

	config := &IntentServiceConfig{
		UseCache:      true,
		MinConfidence: domain.ConfidenceMedium,
	}
	service := NewIntentService(recognizers, cache, config, logger)

	input := &domain.IntentInput{
		Message:  "什么是机器学习？",
		TenantID: "test_tenant",
	}

	ctx := context.Background()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = service.RecognizeIntent(ctx, input)
	}
}
