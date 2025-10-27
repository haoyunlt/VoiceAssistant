package biz

import (
	"context"
	"fmt"
	"strings"
	"time"

	"voiceassistant/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ContextCompressionService 上下文压缩服务
type ContextCompressionService struct {
	aiClient  AIClient
	maxTokens int
	log       *log.Helper
}

// AIClient AI客户端接口
type AIClient interface {
	Generate(ctx context.Context, prompt string, maxTokens int) (string, error)
}

// NewContextCompressionService 创建压缩服务
func NewContextCompressionService(aiClient AIClient, maxTokens int, logger log.Logger) *ContextCompressionService {
	return &ContextCompressionService{
		aiClient:  aiClient,
		maxTokens: maxTokens,
		log:       log.NewHelper(logger),
	}
}

// CompressContext 压缩上下文
func (s *ContextCompressionService) CompressContext(
	ctx context.Context,
	messages []*domain.Message,
	currentTokens int,
) ([]*domain.Message, error) {
	// 1. 如果未超过限制，直接返回
	if currentTokens <= s.maxTokens {
		return messages, nil
	}

	s.log.WithContext(ctx).Infof("Compressing context: %d tokens -> target %d tokens", currentTokens, s.maxTokens)

	// 2. 策略1：保留系统提示和最近N条消息
	systemMessages := s.filterSystemMessages(messages)
	recentMessages := s.getRecentMessages(messages, 10)

	// 3. 计算压缩后的Token数
	compressedTokens := s.estimateTokens(systemMessages) + s.estimateTokens(recentMessages)

	if compressedTokens <= s.maxTokens {
		// 合并消息
		compressed := append(systemMessages, recentMessages...)
		s.log.WithContext(ctx).Infof("Context compressed using strategy 1: %d messages", len(compressed))
		return compressed, nil
	}

	// 4. 策略2：使用LLM总结中间消息
	middleMessages := s.getMiddleMessages(messages)
	if len(middleMessages) > 0 {
		summary, err := s.summarizeMessages(ctx, middleMessages)
		if err != nil {
			s.log.WithContext(ctx).Warnf("Failed to summarize messages: %v", err)
			// 失败时回退到策略1
			return s.compressFallback(systemMessages, recentMessages), nil
		}

		// 5. 构建压缩后的消息列表
		compressed := []*domain.Message{}
		compressed = append(compressed, systemMessages...)

		// 添加总结消息
		summaryMsg := &domain.Message{
			ID:          generateID(),
			Role:        domain.RoleSystem,
			Content:     fmt.Sprintf("Previous conversation summary: %s", summary),
			ContentType: domain.ContentTypeText,
			Tokens:      s.estimateTokens([]*domain.Message{{Content: summary}}),
			CreatedAt:   time.Now(),
		}
		compressed = append(compressed, summaryMsg)
		compressed = append(compressed, recentMessages...)

		s.log.WithContext(ctx).Infof("Context compressed using strategy 2: %d messages with summary", len(compressed))
		return compressed, nil
	}

	// 6. 如果没有中间消息，直接返回系统消息+最近消息
	return s.compressFallback(systemMessages, recentMessages), nil
}

// summarizeMessages 使用LLM总结消息
func (s *ContextCompressionService) summarizeMessages(
	ctx context.Context,
	messages []*domain.Message,
) (string, error) {
	// 构建总结提示
	var sb strings.Builder
	sb.WriteString("Summarize the following conversation concisely, capturing the key points and context:\n\n")

	for _, msg := range messages {
		sb.WriteString(fmt.Sprintf("%s: %s\n", msg.Role, msg.Content))
	}

	sb.WriteString("\nProvide a concise summary (max 200 words) of the key points:")

	// 调用LLM
	summary, err := s.aiClient.Generate(ctx, sb.String(), 300)
	if err != nil {
		return "", fmt.Errorf("failed to generate summary: %w", err)
	}

	return strings.TrimSpace(summary), nil
}

// estimateTokens 估算Token数（简化版）
func (s *ContextCompressionService) estimateTokens(messages []*domain.Message) int {
	totalTokens := 0
	for _, msg := range messages {
		if msg.Tokens > 0 {
			// 如果已经计算过token数，直接使用
			totalTokens += msg.Tokens
		} else {
			// 粗略估算：1 token ≈ 4 字符（中文约2字符）
			totalTokens += len(msg.Content) / 3
		}
	}
	return totalTokens
}

// filterSystemMessages 过滤系统消息
func (s *ContextCompressionService) filterSystemMessages(messages []*domain.Message) []*domain.Message {
	var systemMessages []*domain.Message
	for _, msg := range messages {
		if msg.Role == domain.RoleSystem {
			systemMessages = append(systemMessages, msg)
		}
	}
	return systemMessages
}

// getRecentMessages 获取最近N条非系统消息
func (s *ContextCompressionService) getRecentMessages(messages []*domain.Message, n int) []*domain.Message {
	var nonSystemMessages []*domain.Message

	// 过滤非系统消息
	for _, msg := range messages {
		if msg.Role != domain.RoleSystem {
			nonSystemMessages = append(nonSystemMessages, msg)
		}
	}

	// 获取最近N条
	if len(nonSystemMessages) <= n {
		return nonSystemMessages
	}

	return nonSystemMessages[len(nonSystemMessages)-n:]
}

// getMiddleMessages 获取中间消息（用于总结）
func (s *ContextCompressionService) getMiddleMessages(messages []*domain.Message) []*domain.Message {
	var nonSystemMessages []*domain.Message

	// 过滤非系统消息
	for _, msg := range messages {
		if msg.Role != domain.RoleSystem {
			nonSystemMessages = append(nonSystemMessages, msg)
		}
	}

	// 如果消息数量<=10，没有中间消息
	if len(nonSystemMessages) <= 10 {
		return nil
	}

	// 返回中间部分（排除最近10条）
	return nonSystemMessages[:len(nonSystemMessages)-10]
}

// compressFallback 回退压缩策略
func (s *ContextCompressionService) compressFallback(
	systemMessages []*domain.Message,
	recentMessages []*domain.Message,
) []*domain.Message {
	compressed := make([]*domain.Message, 0, len(systemMessages)+len(recentMessages))
	compressed = append(compressed, systemMessages...)
	compressed = append(compressed, recentMessages...)
	return compressed
}

// generateID 生成ID（简化版）
func generateID() string {
	return fmt.Sprintf("msg_%d", time.Now().UnixNano())
}
