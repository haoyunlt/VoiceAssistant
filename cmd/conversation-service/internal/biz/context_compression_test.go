package biz

import (
	"context"
	"testing"
	"time"

	"voiceassistant/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/stretchr/testify/assert"
)

// MockAIClient 模拟AI客户端
type MockAIClient struct {
	GenerateFunc func(ctx context.Context, prompt string, maxTokens int) (string, error)
}

func (m *MockAIClient) Generate(ctx context.Context, prompt string, maxTokens int) (string, error) {
	if m.GenerateFunc != nil {
		return m.GenerateFunc(ctx, prompt, maxTokens)
	}
	return "This is a summary of the conversation.", nil
}

func TestContextCompression_UnderLimit(t *testing.T) {
	// 准备测试数据
	mockAI := &MockAIClient{}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 1000, logger)

	messages := []*domain.Message{
		{
			ID:      "1",
			Role:    domain.RoleUser,
			Content: "Hello",
			Tokens:  5,
		},
		{
			ID:      "2",
			Role:    domain.RoleAssistant,
			Content: "Hi there!",
			Tokens:  10,
		},
	}

	currentTokens := 15

	// 执行压缩
	compressed, err := service.CompressContext(context.Background(), messages, currentTokens)

	// 验证结果
	assert.NoError(t, err)
	assert.Equal(t, 2, len(compressed))
	assert.Equal(t, messages, compressed)
}

func TestContextCompression_OverLimit_Strategy1(t *testing.T) {
	// 准备测试数据
	mockAI := &MockAIClient{}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 100, logger)

	messages := []*domain.Message{
		{
			ID:      "sys",
			Role:    domain.RoleSystem,
			Content: "You are a helpful assistant.",
			Tokens:  20,
		},
	}

	// 添加15条消息
	for i := 0; i < 15; i++ {
		messages = append(messages, &domain.Message{
			ID:      string(rune(i)),
			Role:    domain.RoleUser,
			Content: "Test message",
			Tokens:  10,
		})
	}

	currentTokens := 170

	// 执行压缩
	compressed, err := service.CompressContext(context.Background(), messages, currentTokens)

	// 验证结果
	assert.NoError(t, err)
	// 应该保留系统消息 + 最近10条，或者使用了策略2（系统消息 + 总结 + 最近10条 = 12条）
	assert.LessOrEqual(t, len(compressed), 12)
	assert.GreaterOrEqual(t, len(compressed), 11)
	// 第一条应该是系统消息
	assert.Equal(t, domain.RoleSystem, compressed[0].Role)
}

func TestContextCompression_OverLimit_Strategy2(t *testing.T) {
	// 准备测试数据
	mockAI := &MockAIClient{
		GenerateFunc: func(ctx context.Context, prompt string, maxTokens int) (string, error) {
			return "Summary of previous conversation", nil
		},
	}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 50, logger)

	messages := []*domain.Message{
		{
			ID:      "sys",
			Role:    domain.RoleSystem,
			Content: "You are a helpful assistant.",
			Tokens:  20,
		},
	}

	// 添加20条消息（触发策略2）
	for i := 0; i < 20; i++ {
		messages = append(messages, &domain.Message{
			ID:        string(rune(i)),
			Role:      domain.RoleUser,
			Content:   "Test message number " + string(rune(i)),
			Tokens:    15,
			CreatedAt: time.Now().Add(time.Duration(i) * time.Minute),
		})
	}

	currentTokens := 320

	// 执行压缩
	compressed, err := service.CompressContext(context.Background(), messages, currentTokens)

	// 验证结果
	assert.NoError(t, err)
	// 应该包含：系统消息 + 总结消息 + 最近10条
	assert.GreaterOrEqual(t, len(compressed), 12)

	// 检查是否包含总结消息
	foundSummary := false
	for _, msg := range compressed {
		if msg.Role == domain.RoleSystem && msg.ID != "sys" {
			foundSummary = true
			break
		}
	}
	assert.True(t, foundSummary, "Should contain summary message")
}

func TestEstimateTokens(t *testing.T) {
	mockAI := &MockAIClient{}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 1000, logger)

	messages := []*domain.Message{
		{Content: "Hello", Tokens: 0},
		{Content: "World", Tokens: 10},
	}

	tokens := service.estimateTokens(messages)

	// "Hello" (5 chars / 3 ≈ 1) + 10 = 11
	assert.GreaterOrEqual(t, tokens, 10)
}

func TestFilterSystemMessages(t *testing.T) {
	mockAI := &MockAIClient{}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 1000, logger)

	messages := []*domain.Message{
		{Role: domain.RoleSystem, Content: "System 1"},
		{Role: domain.RoleUser, Content: "User 1"},
		{Role: domain.RoleSystem, Content: "System 2"},
		{Role: domain.RoleAssistant, Content: "Assistant 1"},
	}

	systemMessages := service.filterSystemMessages(messages)

	assert.Equal(t, 2, len(systemMessages))
	assert.Equal(t, domain.RoleSystem, systemMessages[0].Role)
	assert.Equal(t, domain.RoleSystem, systemMessages[1].Role)
}

func TestGetRecentMessages(t *testing.T) {
	mockAI := &MockAIClient{}
	logger := log.DefaultLogger
	service := NewContextCompressionService(mockAI, 1000, logger)

	messages := []*domain.Message{
		{Role: domain.RoleSystem, Content: "System"},
		{Role: domain.RoleUser, Content: "User 1"},
		{Role: domain.RoleUser, Content: "User 2"},
		{Role: domain.RoleUser, Content: "User 3"},
	}

	recent := service.getRecentMessages(messages, 2)

	// 应该返回最近2条非系统消息
	assert.Equal(t, 2, len(recent))
	assert.Equal(t, "User 2", recent[0].Content)
	assert.Equal(t, "User 3", recent[1].Content)
}
